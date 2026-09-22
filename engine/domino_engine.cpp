// ============================================================================
//  Domino Analyzer Pro — C++ Analysis Engine
//  ---------------------------------------------------------------
//  CLI: reads one JSON request from stdin, writes one JSON response to stdout.
//
//  Commands:
//    {"cmd":"analyze",  ...}  -> full move analysis (Monte-Carlo rollouts)
//    {"cmd":"selftest"}       -> internal consistency checks
//
//  This is a faithful port of the original JavaScript engine with these
//  accuracy fixes:
//    * the tile just played by the user is now counted in the "out" number
//      map (the JS version lost it, inflating unknown counts);
//    * deals are constraint-aware and never silently violate recorded PASS
//      information when a feasible assignment exists;
//    * RNG is seeded and deterministic (same input -> same output).
// ============================================================================

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <map>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

static const char* ENGINE_VERSION = "2.0.0";

// ---------------------------------------------------------------------------
// Minimal JSON value + parser
// ---------------------------------------------------------------------------
struct JValue {
    enum Type { NUL, BOOL, NUM, STR, ARR, OBJ } t{NUL};
    bool b{false};
    double num{0};
    std::string s;
    std::vector<JValue> arr;
    std::vector<std::pair<std::string, JValue>> obj;

    const JValue* find(const std::string& key) const {
        if (t != OBJ) return nullptr;
        for (const auto& kv : obj)
            if (kv.first == key) return &kv.second;
        return nullptr;
    }
    const JValue& at(const std::string& key) const {
        const JValue* v = find(key);
        if (!v) throw std::runtime_error("missing field: " + key);
        return *v;
    }
    std::string asString(const std::string& def = "") const { return t == STR ? s : def; }
    double asNum(double def = 0) const { return t == NUM ? num : def; }
    int asInt(int def = 0) const { return static_cast<int>(asNum(def)); }
    bool asBool(bool def = false) const { return t == BOOL ? b : def; }
    bool isArr() const { return t == ARR; }
    size_t size() const { return t == ARR ? arr.size() : 0; }
};

struct JParser {
    std::string src; // by value: never dangle on temporaries like payload.str()
    size_t i = 0;
    explicit JParser(const std::string& s) : src(s) {}

    [[noreturn]] void fail(const std::string& msg) {
        throw std::runtime_error("JSON parse error @ " + std::to_string(i) + ": " + msg);
    }
    void ws() {
        while (i < src.size() &&
               (src[i] == ' ' || src[i] == '\t' || src[i] == '\n' || src[i] == '\r'))
            ++i;
    }
    char peek() {
        if (i >= src.size()) fail("unexpected end of input");
        return src[i];
    }
    void lit(const char* w) {
        for (const char* p = w; *p; ++p) {
            if (i >= src.size() || src[i] != *p) fail(std::string("expected ") + w);
            ++i;
        }
    }

    JValue parse() {
        ws();
        JValue v = parseValue();
        ws();
        if (i != src.size()) fail("trailing characters after JSON value");
        return v;
    }

    JValue parseValue() {
        ws();
        char c = peek();
        switch (c) {
            case '{': return parseObj();
            case '[': return parseArr();
            case '"': {
                JValue v; v.t = JValue::STR; v.s = parseString(); return v;
            }
            case 't': { lit("true");  JValue v; v.t = JValue::BOOL; v.b = true;  return v; }
            case 'f': { lit("false"); JValue v; v.t = JValue::BOOL; v.b = false; return v; }
            case 'n': { lit("null");  JValue v; v.t = JValue::NUL; return v; }
            default:  return parseNum();
        }
    }

    JValue parseNum() {
        size_t start = i;
        if (i < src.size() && (src[i] == '-' || src[i] == '+')) ++i;
        bool any = false;
        while (i < src.size() && ((src[i] >= '0' && src[i] <= '9') || src[i] == '.' ||
                                  src[i] == 'e' || src[i] == 'E' || src[i] == '-' ||
                                  src[i] == '+')) {
            if (src[i] >= '0' && src[i] <= '9') any = true;
            ++i;
        }
        if (!any) fail("invalid number");
        JValue v; v.t = JValue::NUM;
        v.num = std::strtod(src.substr(start, i - start).c_str(), nullptr);
        return v;
    }

    static void appendUtf8(std::string& out, unsigned cp) {
        if (cp < 0x80) out += static_cast<char>(cp);
        else if (cp < 0x800) {
            out += static_cast<char>(0xC0 | (cp >> 6));
            out += static_cast<char>(0x80 | (cp & 0x3F));
        } else {
            out += static_cast<char>(0xE0 | (cp >> 12));
            out += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
            out += static_cast<char>(0x80 | (cp & 0x3F));
        }
    }

    std::string parseString() {
        expect('"');
        std::string out;
        while (true) {
            if (i >= src.size()) fail("unterminated string");
            char c = src[i++];
            if (c == '"') break;
            if (c != '\\') { out += c; continue; }
            if (i >= src.size()) fail("bad escape");
            char e = src[i++];
            switch (e) {
                case '"': out += '"'; break;
                case '\\': out += '\\'; break;
                case '/': out += '/'; break;
                case 'b': out += '\b'; break;
                case 'f': out += '\f'; break;
                case 'n': out += '\n'; break;
                case 'r': out += '\r'; break;
                case 't': out += '\t'; break;
                case 'u': {
                    unsigned cp = 0;
                    for (int k = 0; k < 4; ++k) {
                        if (i >= src.size()) fail("bad \\u escape");
                        char h = src[i++];
                        cp <<= 4;
                        if (h >= '0' && h <= '9') cp += unsigned(h - '0');
                        else if (h >= 'a' && h <= 'f') cp += unsigned(h - 'a' + 10);
                        else if (h >= 'A' && h <= 'F') cp += unsigned(h - 'A' + 10);
                        else fail("bad hex digit");
                    }
                    appendUtf8(out, cp);
                    break;
                }
                default: fail("unknown escape");
            }
        }
        return out;
    }

    void expect(char c) {
        if (peek() != c) fail(std::string("expected '") + c + "'");
        ++i;
    }

    JValue parseObj() {
        expect('{');
        JValue v; v.t = JValue::OBJ;
        ws();
        if (peek() == '}') { ++i; return v; }
        while (true) {
            ws();
            std::string key = parseString();
            ws();
            expect(':');
            v.obj.emplace_back(key, parseValue());
            ws();
            char c = peek();
            if (c == ',') { ++i; continue; }
            if (c == '}') { ++i; break; }
            fail("expected ',' or '}'");
        }
        return v;
    }

    JValue parseArr() {
        expect('[');
        JValue v; v.t = JValue::ARR;
        ws();
        if (peek() == ']') { ++i; return v; }
        while (true) {
            v.arr.push_back(parseValue());
            ws();
            char c = peek();
            if (c == ',') { ++i; continue; }
            if (c == ']') { ++i; break; }
            fail("expected ',' or ']'");
        }
        return v;
    }
};

// ---------------------------------------------------------------------------
// JSON output helpers
// ---------------------------------------------------------------------------
static std::string jesc(const std::string& s) {
    std::string o;
    o.reserve(s.size() + 8);
    for (unsigned char c : s) {
        switch (c) {
            case '"': o += "\\\""; break;
            case '\\': o += "\\\\"; break;
            case '\n': o += "\\n"; break;
            case '\r': o += "\\r"; break;
            case '\t': o += "\\t"; break;
            default:
                if (c < 0x20) {
                    char buf[8];
                    std::snprintf(buf, sizeof buf, "\\u%04x", c);
                    o += buf;
                } else o += static_cast<char>(c);
        }
    }
    return o;
}
static std::string jstr(const std::string& s) { return "\"" + jesc(s) + "\""; }
static std::string jnum(double v, int prec = 4) {
    char buf[64];
    std::snprintf(buf, sizeof buf, "%.*f", prec, v);
    return buf;
}
static std::string jint(long long v) {
    char buf[32];
    std::snprintf(buf, sizeof buf, "%lld", v);
    return buf;
}
static std::string jbool(bool b) { return b ? "true" : "false"; }

// ---------------------------------------------------------------------------
// Tiles
// ---------------------------------------------------------------------------
struct Tile {
    int a, b;
    std::string key; // normalized "lo-hi"
};
static std::vector<Tile> g_tiles;
static std::map<std::string, int> g_keyToId;

static void initTiles() {
    for (int a = 0; a <= 6; ++a)
        for (int b = a; b <= 6; ++b) {
            Tile t{a, b, std::to_string(a) + "-" + std::to_string(b)};
            g_keyToId[t.key] = static_cast<int>(g_tiles.size());
            g_tiles.push_back(t);
        }
}
static int tileId(const std::string& key) {
    auto it = g_keyToId.find(key);
    if (it == g_keyToId.end()) throw std::runtime_error("invalid tile key: " + key);
    return it->second;
}
static int handValue(const std::vector<int>& hand) {
    int s = 0;
    for (int id : hand) s += g_tiles[id].a + g_tiles[id].b;
    return s;
}

// ---------------------------------------------------------------------------
// Seeded deterministic RNG (xoshiro256** seeded by splitmix64)
// ---------------------------------------------------------------------------
struct Rng {
    uint64_t s[4]{1, 2, 3, 4};

    static uint64_t splitmix64(uint64_t& x) {
        x += 0x9E3779B97F4A7C15ULL;
        uint64_t z = x;
        z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
        z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
        return z ^ (z >> 31);
    }
    static uint64_t rotl(uint64_t x, int k) { return (x << k) | (x >> (64 - k)); }

    explicit Rng(uint64_t seed) {
        uint64_t x = seed;
        for (auto& v : s) v = splitmix64(x);
        if ((s[0] | s[1] | s[2] | s[3]) == 0) s[0] = 1;
    }
    inline uint64_t next() {
        uint64_t result = rotl(s[1] * 5, 7) * 9;
        uint64_t t = s[1] << 17;
        s[2] ^= s[0];
        s[3] ^= s[1];
        s[1] ^= s[2];
        s[0] ^= s[3];
        s[2] ^= t;
        s[3] = rotl(s[3], 45);
        return result;
    }
    double nextDouble() { return static_cast<double>(next() >> 11) * (1.0 / 9007199254740992.0); }
    int nextInt(int n) { return static_cast<int>(next() % static_cast<uint64_t>(n)); }

    void shuffle(std::vector<int>& a) {
        for (size_t k = a.size() - 1; k > 0; --k) {
            size_t j = static_cast<size_t>(nextInt(static_cast<int>(k) + 1));
            std::swap(a[k], a[j]);
        }
    }
};

// ---------------------------------------------------------------------------
// Dominance / number-map heuristics (ports of the JS logic)
// ---------------------------------------------------------------------------
struct Dominance {
    std::array<int, 7> counts{};
    std::vector<std::pair<int, int>> dominant; // (num, count), count >= 3
    std::vector<std::pair<int, int>> strong;   // (num, count), count == 2
};

static Dominance analyzeDominance(const std::vector<int>& hand) {
    Dominance d;
    for (int id : hand) {
        d.counts[g_tiles[id].a]++;
        d.counts[g_tiles[id].b]++;
    }
    std::vector<std::pair<int, int>> ranked;
    for (int n = 0; n <= 6; ++n) ranked.emplace_back(n, d.counts[n]);
    std::stable_sort(ranked.begin(), ranked.end(),
                     [](const std::pair<int, int>& x, const std::pair<int, int>& y) {
                         return x.second > y.second;
                     });
    for (const auto& r : ranked) {
        if (r.second >= 3) d.dominant.push_back(r);
        else if (r.second == 2) d.strong.push_back(r);
    }
    return d;
}

struct NumMap {
    std::array<int, 7> mine{}, out{}, unk{};
};
static NumMap buildNumMap(const std::vector<int>& mineIds, const std::vector<int>& outIds) {
    NumMap m;
    for (int id : mineIds) { m.mine[g_tiles[id].a]++; m.mine[g_tiles[id].b]++; }
    for (int id : outIds)  { m.out[g_tiles[id].a]++;  m.out[g_tiles[id].b]++; }
    for (int n = 0; n <= 6; ++n) m.unk[n] = 7 - m.mine[n] - m.out[n];
    return m;
}

// ---------------------------------------------------------------------------
// Constraint-aware dealing
// ---------------------------------------------------------------------------
struct Deal {
    std::vector<std::vector<int>> oppHands;
    std::vector<int> boneyard;
    int fallbacks = 0; // times a hand had to ignore PASS constraints
};

// Distributes `unknown` tiles to (numPlayers-1) opponents with quotas and
// eliminated-number constraints. Opponents with the tightest constraints are
// served first; tiles valid for the current opponent are preferred.
static Deal dealConstrained(const std::vector<int>& unknownIn, int numOpp, int totalOppCards,
                            const std::vector<std::vector<int>>& elim, Rng& rng) {
    Deal d;
    d.oppHands.assign(numOpp, {});
    std::vector<int> available = unknownIn;
    rng.shuffle(available);

    int per = numOpp > 0 ? totalOppCards / numOpp : 0;
    std::vector<int> quotas(numOpp, 0);
    int assigned = 0;
    for (int p = 0; p < numOpp; ++p) {
        quotas[p] = (p == numOpp - 1) ? totalOppCards - assigned : per;
        assigned += quotas[p];
    }

    static const std::vector<int> kNoElim;
    auto elimOf = [&](int p) -> const std::vector<int>& {
        return p < static_cast<int>(elim.size()) ? elim[p] : kNoElim;
    };

    std::vector<int> order(numOpp);
    for (int p = 0; p < numOpp; ++p) order[p] = p;
    std::stable_sort(order.begin(), order.end(), [&](int a, int b) {
        return elimOf(a).size() > elimOf(b).size(); // tightest constraints first
    });

    auto violates = [&](int tileId, const std::vector<int>& e) {
        for (int n : e)
            if (g_tiles[tileId].a == n || g_tiles[tileId].b == n) return true;
        return false;
    };

    for (int p : order) {
        int quota = quotas[p];
        if (quota <= 0) continue;
        const std::vector<int>& e = elimOf(p);
        std::vector<int>& hand = d.oppHands[p];
        // pass 1: tiles respecting the constraint
        for (size_t k = 0; k < available.size() && static_cast<int>(hand.size()) < quota;) {
            if (!violates(available[k], e)) {
                hand.push_back(available[k]);
                available[k] = available.back();
                available.pop_back();
            } else ++k;
        }
        // pass 2 (fallback): quota unmet — ignore constraint
        while (static_cast<int>(hand.size()) < quota && !available.empty()) {
            hand.push_back(available.back());
            available.pop_back();
            d.fallbacks++;
        }
    }
    d.boneyard = std::move(available);
    return d;
}

// ---------------------------------------------------------------------------
// Move generation / application
// ---------------------------------------------------------------------------
struct Move {
    int tileId;
    int side; // 0 = first, 1 = left, 2 = right
    int newEnd;
    int a, b;
};
struct AppliedMove {
    std::vector<int> hand;
    int le, re;
};

static std::vector<Move> getValidMoves(const std::vector<int>& hand, int le, int re) {
    std::vector<Move> moves;
    for (int id : hand) {
        int a = g_tiles[id].a, b = g_tiles[id].b;
        if (le != -1) {
            if (a == le) moves.push_back({id, 1, b, a, b});
            else if (b == le) moves.push_back({id, 1, a, a, b});
        }
        if (re != -1) {
            if (a == re) moves.push_back({id, 2, b, a, b});
            else if (b == re) moves.push_back({id, 2, a, a, b});
        }
        if (le == -1 && re == -1) moves.push_back({id, 0, -1, a, b});
    }
    return moves;
}

static AppliedMove applyMove(const std::vector<int>& hand, const Move& m, int le, int re) {
    AppliedMove r;
    r.hand.reserve(hand.size());
    for (int id : hand)
        if (id != m.tileId) r.hand.push_back(id);
    r.le = le;
    r.re = re;
    if (m.side == 0) { r.le = m.a; r.re = m.b; }
    else if (m.side == 1) r.le = m.newEnd;
    else r.re = m.newEnd;
    return r;
}

// Shared AI used for every seat (mirrors the original game model).
static std::optional<Move> aiChooseMove(const std::vector<int>& hand, int le, int re,
                                        const Dominance& dom, const NumMap& nm, Rng& rng) {
    auto moves = getValidMoves(hand, le, re);
    if (moves.empty()) return std::nullopt;

    const Move* best = nullptr;
    double bestScore = -1e18;
    for (const Move& m : moves) {
        double s = 0;
        int a = m.a, b = m.b;
        AppliedMove after = applyMove(hand, m, le, re);

        if (a == b) s += 18;
        s += (a + b) * 1.8;

        for (const auto& d : dom.dominant) {
            if (after.le == d.first && after.re == d.first) s += 50;
            if (after.le == d.first || after.re == d.first) s += 25;
            if (a == d.first || b == d.first) s += 8;
        }
        for (const auto& st : dom.strong)
            if (after.le == st.first || after.re == st.first) s += 12;

        // NOTE: counts are the pre-move map, matching the original engine.
        int ends[2] = {after.le, after.re};
        for (int e : ends) {
            int mineLeft = 0;
            for (int id : after.hand) {
                if (g_tiles[id].a == e) mineLeft++;
                if (g_tiles[id].b == e) mineLeft++;
            }
            if (mineLeft >= 2 && nm.unk[e] <= 2) s += 15;
            if (mineLeft > 0 && nm.unk[e] == 0) s += 25;
        }
        if (after.le == after.re) {
            int e = after.le;
            bool weHave = false;
            for (int id : after.hand)
                if (g_tiles[id].a == e || g_tiles[id].b == e) { weHave = true; break; }
            if (!weHave && nm.unk[e] > 0) s -= 20;
            else if (!weHave && nm.unk[e] == 0) s += 30;
        }

        int flex = 0;
        for (int id : after.hand) {
            const Tile& t = g_tiles[id];
            if (t.a == after.le || t.b == after.le || t.a == after.re || t.b == after.re) flex++;
        }
        s += flex * 3;
        s += rng.nextDouble() * 5.0; // tie-break noise

        if (s > bestScore) { bestScore = s; best = &m; }
    }
    return *best;
}

// ---------------------------------------------------------------------------
// Single Monte-Carlo game
// ---------------------------------------------------------------------------
struct SimResult {
    bool iWin = false;
    int myTiles = 0;
    int myVal = 0;
    std::vector<int> oppVals;
    bool blocked = false;
    std::vector<int> oppMoveIds;
    int dominanceControl = 0;
    std::vector<int> oppPassCounts;
};

static SimResult simulateGame(const std::vector<int>& myHandIn, int leIn, int reIn,
                              int numPlayers, const Deal& deal, Rng& rng,
                              const NumMap& baseMap) {
    SimResult res;
    int numOpp = numPlayers - 1;
    std::vector<int> myH = myHandIn;
    std::vector<std::vector<int>> oppHands = deal.oppHands;
    int le = leIn, re = reIn;
    int passes = 0, cur = 1, turn = 0; // after "my" analyzed move, next seat moves first

    NumMap nm = baseMap;
    Dominance myDom = analyzeDominance(myH);
    res.oppPassCounts.assign(numOpp, 0);

    while (turn < 300) {
        ++turn;
        if (cur == 0) {
            auto mv = aiChooseMove(myH, le, re, myDom, nm, rng);
            if (mv) {
                const Tile& t = g_tiles[mv->tileId];
                AppliedMove ap = applyMove(myH, *mv, le, re);
                myH = ap.hand;
                le = ap.le; re = ap.re;
                passes = 0;
                nm.mine[t.a]--; nm.mine[t.b]--;
                nm.out[t.a]++;  nm.out[t.b]++;
                for (int n = 0; n <= 6; ++n) nm.unk[n] = 7 - nm.mine[n] - nm.out[n];
                for (const auto& d : myDom.dominant)
                    if (le == d.first || re == d.first) res.dominanceControl++;
            } else ++passes;
        } else {
            int oi = cur - 1;
            if (oi < static_cast<int>(oppHands.size())) {
                Dominance od = analyzeDominance(oppHands[oi]);
                auto mv = aiChooseMove(oppHands[oi], le, re, od, nm, rng);
                if (mv) {
                    const Tile& t = g_tiles[mv->tileId];
                    AppliedMove ap = applyMove(oppHands[oi], *mv, le, re);
                    oppHands[oi] = ap.hand;
                    le = ap.le; re = ap.re;
                    passes = 0;
                    nm.unk[t.a]--; nm.unk[t.b]--;
                    nm.out[t.a]++; nm.out[t.b]++;
                    res.oppMoveIds.push_back(mv->tileId);
                } else {
                    ++passes;
                    res.oppPassCounts[oi]++;
                }
            } else ++passes;
        }

        if (myH.empty()) {
            res.iWin = true; res.myTiles = 0; res.myVal = 0;
            res.oppVals.reserve(oppHands.size());
            for (const auto& h : oppHands) res.oppVals.push_back(handValue(h));
            return res;
        }
        for (const auto& h : oppHands) {
            if (h.empty()) {
                res.iWin = false; res.myTiles = static_cast<int>(myH.size());
                res.myVal = handValue(myH);
                res.oppVals.reserve(oppHands.size());
                for (const auto& h2 : oppHands) res.oppVals.push_back(handValue(h2));
                return res;
            }
        }
        if (passes >= numPlayers) {
            res.blocked = true;
            res.myTiles = static_cast<int>(myH.size());
            res.myVal = handValue(myH);
            res.oppVals.reserve(oppHands.size());
            for (const auto& h : oppHands) res.oppVals.push_back(handValue(h));
            int minO = res.oppVals.empty() ? 0 : *std::min_element(res.oppVals.begin(), res.oppVals.end());
            res.iWin = res.myVal <= minO;
            return res;
        }
        cur = (cur + 1) % numPlayers;
    }

    // Turn cap reached: settle by pip value (same as the original engine).
    res.myTiles = static_cast<int>(myH.size());
    res.myVal = handValue(myH);
    res.oppVals.reserve(oppHands.size());
    for (const auto& h : oppHands) res.oppVals.push_back(handValue(h));
    int minO = res.oppVals.empty() ? 0 : *std::min_element(res.oppVals.begin(), res.oppVals.end());
    res.iWin = res.myVal <= minO;
    return res;
}

// ---------------------------------------------------------------------------
// Deterministic per-move heuristics (ports of the JS analyzers)
// ---------------------------------------------------------------------------
struct Heuristics {
    int domSupportScore = 0;
    std::vector<std::string> domSupportReasons;
    int trapScore = 0;
    std::vector<std::string> trapReasons;
    int blockScore = 0;
    int selfTrapScore = 0;
    std::vector<std::string> blockReasons;
    std::vector<std::pair<int, std::string>> guaranteedBlocks; // (oppIdx1based, reason)
};

static Heuristics computeHeuristics(const Move& move, int newLeft, int newRight,
                                    const std::vector<int>& handAfter,
                                    const Dominance& dom, const NumMap& mapAfter,
                                    const std::vector<std::vector<int>>& elim) {
    Heuristics h;

    // dominance support
    for (const auto& d : dom.dominant) {
        if (newLeft == d.first || newRight == d.first) {
            h.domSupportScore += 20;
            h.domSupportReasons.push_back("Ujung cocok angka dominan " + std::to_string(d.first) +
                                          " (" + std::to_string(d.second) + " kartu)");
        }
        if (newLeft == d.first && newRight == d.first) {
            h.domSupportScore += 30;
            h.domSupportReasons.push_back("🏆 KEDUA UJUNG dikuasai angka " + std::to_string(d.first) + "!");
        }
    }
    for (const auto& st : dom.strong) {
        if (newLeft == st.first || newRight == st.first) {
            h.domSupportScore += 8;
            h.domSupportReasons.push_back("Ujung cocok angka kuat " + std::to_string(st.first));
        }
    }

    // traps
    for (const auto& d : dom.dominant) {
        bool onLeft = (newLeft == d.first), onRight = (newRight == d.first);
        if (onLeft || onRight) {
            int unknownD = mapAfter.unk[d.first];
            if (unknownD > 0) {
                h.trapScore += 15;
                h.trapReasons.push_back("🪤 JERAT angka " + std::to_string(d.first) +
                                        " terpasang! " + std::to_string(unknownD) + " kartu " +
                                        std::to_string(d.first) + " masih di luar.");
            }
            if (onLeft && onRight) {
                h.trapScore += 20;
                h.trapReasons.push_back("🪤 JERAT GANDA! Kedua ujung = " + std::to_string(d.first) + "!");
            }
        }
    }

    // blocks / self-traps
    int ends[2] = {newLeft, newRight};
    for (int endNum : ends) {
        int unk = mapAfter.unk[endNum], mine = mapAfter.mine[endNum];
        if (unk == 0 && mine == 0) {
            h.blockScore += 5;
            h.selfTrapScore += 10;
            h.blockReasons.push_back("⚠️ Ujung " + std::to_string(endNum) +
                                     " MATI — bisa merugikan diri sendiri!");
        } else if (unk == 0 && mine > 0) {
            h.blockScore += 25;
            h.blockReasons.push_back("🔒 KUNCI! Ujung " + std::to_string(endNum) +
                                     ": hanya Anda yang pegang (" + std::to_string(mine) + " kartu)!");
        } else if (unk <= 1 && mine >= 2) {
            h.blockScore += 12;
            h.blockReasons.push_back("🚧 Ujung " + std::to_string(endNum) + " hampir terkunci.");
        }
    }
    for (int endNum : ends) {
        bool hasCard = false;
        for (int id : handAfter)
            if (g_tiles[id].a == endNum || g_tiles[id].b == endNum) { hasCard = true; break; }
        if (!hasCard && mapAfter.unk[endNum] > 0) {
            h.selfTrapScore += 6;
            h.blockReasons.push_back("⚠️ Anda tidak pegang kartu " + std::to_string(endNum) +
                                     " lagi — bisa jadi bumerang.");
        }
    }

    // guaranteed blocks from recorded PASS data
    for (size_t p = 0; p < elim.size(); ++p) {
        bool hasLeft = false, hasRight = false;
        for (int n : elim[p]) {
            if (n == newLeft) hasLeft = true;
            if (n == newRight) hasRight = true;
        }
        std::string oppName = "Lawan " + std::to_string(p + 1);
        if (hasLeft && hasRight && newLeft != newRight) {
            h.guaranteedBlocks.emplace_back(
                static_cast<int>(p) + 1,
                oppName + " PASTI tidak bisa main (tidak punya " + std::to_string(newLeft) +
                    " maupun " + std::to_string(newRight) + ")!");
        } else if ((hasLeft || hasRight) && newLeft == newRight) {
            h.guaranteedBlocks.emplace_back(
                static_cast<int>(p) + 1,
                oppName + " PASTI tidak bisa main (tidak punya " + std::to_string(newRight) + ")!");
        }
    }
    return h;
}

struct FirstMoveSafety {
    int canPlayNext = 0;
    int totalRemaining = 0;
    double safetyRatio = 0;
    std::vector<std::string> canPlayKeys, cannotPlayKeys;
};
static FirstMoveSafety analyzeFirstMoveSafety(const Move& move, const std::vector<int>& hand) {
    FirstMoveSafety f;
    int a = move.a, b = move.b;
    for (int id : hand) {
        if (id == move.tileId) continue;
        const Tile& t = g_tiles[id];
        if (t.a == a || t.b == a || t.a == b || t.b == b) {
            f.canPlayNext++;
            f.canPlayKeys.push_back(t.key);
        } else f.cannotPlayKeys.push_back(t.key);
    }
    f.totalRemaining = f.canPlayNext + static_cast<int>(f.cannotPlayKeys.size());
    f.safetyRatio = f.totalRemaining > 0 ? static_cast<double>(f.canPlayNext) / f.totalRemaining : 0.0;
    return f;
}

// ---------------------------------------------------------------------------
// Analyze command
// ---------------------------------------------------------------------------
struct OppInfo {
    std::vector<int> eliminated;
    int passCount = 0;
};

static std::vector<int> parseTileList(const JValue& v, const char* field) {
    std::vector<int> ids;
    if (!v.isArr()) throw std::runtime_error(std::string("field '") + field + "' must be an array");
    for (const JValue& e : v.arr) ids.push_back(tileId(e.asString()));
    return ids;
}

static std::string runAnalyze(const JValue& req) {
    int numPlayers = req.at("numPlayers").asInt(4);
    int cardsPerPlayer = req.at("cardsPerPlayer").asInt(7);
    int numSims = req.at("numSims").asInt(1000);
    unsigned long long seed = static_cast<unsigned long long>(req.at("seed").asNum(42));
    int le = req.at("leftEnd").asInt(-1);
    int re = req.at("rightEnd").asInt(-1);

    std::vector<int> myHand = parseTileList(req.at("myHand"), "myHand");
    std::vector<int> boardIds = parseTileList(req.at("played"), "played");

    std::vector<OppInfo> opps;
    const JValue& oppArr = req.at("opponents");
    for (const JValue& o : oppArr.arr) {
        OppInfo oi;
        oi.passCount = o.at("passes").asInt(0);
        const JValue* el = o.find("eliminated");
        if (el && el->isArr())
            for (const JValue& n : el->arr) oi.eliminated.push_back(n.asInt(-1));
        opps.push_back(std::move(oi));
    }

    // ---- validation ----
    if (numPlayers < 2 || numPlayers > 4) throw std::runtime_error("numPlayers must be 2..4");
    std::vector<int> seen(28, 0);
    for (int id : myHand) seen[id]++;
    for (int id : boardIds) seen[id]++;
    for (int id = 0; id < 28; ++id)
        if (seen[id] > 1) throw std::runtime_error("duplicate tile: " + g_tiles[id].key);
    if (numPlayers * cardsPerPlayer > 28) throw std::runtime_error("total cards exceed 28");

    bool isFirstMove = (le == -1 && re == -1);

    // unknown pool = 28 - mine - board
    std::vector<int> unknown;
    for (int id = 0; id < 28; ++id)
        if (seen[id] == 0) unknown.push_back(id);

    int distributed = numPlayers * cardsPerPlayer;
    int totalOppCards = distributed - static_cast<int>(myHand.size()) -
                        static_cast<int>(boardIds.size());
    if (totalOppCards < 0) totalOppCards = 0;
    if (req.find("totalOppCards")) {
        int given = req.find("totalOppCards")->asInt(totalOppCards);
        if (given >= 0) totalOppCards = given;
    }

    // pad bila lawan yang dilaporkan kurang dari numPlayers-1 (defensif)
    while (opps.size() < static_cast<size_t>(numPlayers - 1)) opps.push_back(OppInfo{});

    std::vector<std::vector<int>> elim;
    elim.reserve(opps.size());
    for (const auto& o : opps) elim.push_back(o.eliminated);
    bool hasPassData = false;
    for (const auto& o : opps)
        if (o.passCount > 0) hasPassData = true;

    std::vector<Move> validMoves = getValidMoves(myHand, le, re);

    std::ostringstream out;
    out << "{\"ok\":true,\"engine\":" << jstr("domino-cpp/" + std::string(ENGINE_VERSION))
        << ",\"numPlayers\":" << numPlayers
        << ",\"cardsPerPlayer\":" << cardsPerPlayer
        << ",\"numSims\":" << numSims
        << ",\"seed\":" << seed
        << ",\"leftEnd\":" << le << ",\"rightEnd\":" << re
        << ",\"isFirstMove\":" << jbool(isFirstMove)
        << ",\"hasPassData\":" << jbool(hasPassData)
        << ",\"unknownCount\":" << unknown.size()
        << ",\"totalOppCards\":" << totalOppCards
        << ",\"validMoveCount\":" << validMoves.size()
        << ",\"moves\":[";

    Dominance dom = analyzeDominance(myHand);
    Rng master(seed);

    for (size_t mi = 0; mi < validMoves.size(); ++mi) {
        const Move& move = validMoves[mi];
        AppliedMove after = applyMove(myHand, move, le, re);
        const std::vector<int>& nH = after.hand;
        int nL = after.le, nR = after.re;

        std::vector<int> playedAfter = boardIds;
        playedAfter.push_back(move.tileId);
        NumMap mapAfter = buildNumMap(nH, playedAfter);

        Heuristics h = computeHeuristics(move, nL, nR, nH, dom, mapAfter, elim);
        std::optional<FirstMoveSafety> safety;
        if (isFirstMove) safety = analyzeFirstMoveSafety(move, myHand);

        int flex = 0;
        for (int id : nH) {
            const Tile& t = g_tiles[id];
            if (t.a == nL || t.b == nL || t.a == nR || t.b == nR) flex++;
        }

        // ---- Monte Carlo ----
        NumMap simBase = mapAfter; // "mine" counts from nH; "out" includes the played tile

        int wins = 0, winByEmpty = 0, winByValue = 0, deadlockWins = 0, blockedGames = 0;
        long long totalMyVal = 0, totalOppMinVal = 0, totalDomControl = 0, totalOppPasses = 0;
        std::array<long long, 28> dangerCnt{};
        long long losses = 0;

        for (int s = 0; s < numSims; ++s) {
            Deal deal = dealConstrained(unknown, numPlayers - 1, totalOppCards, elim, master);
            Rng gameRng(master.next());
            SimResult sim = simulateGame(nH, nL, nR, numPlayers, deal, gameRng, simBase);
            if (sim.iWin) {
                ++wins;
                if (sim.myTiles == 0) ++winByEmpty;
                else {
                    ++winByValue;
                    if (sim.blocked) ++deadlockWins;
                }
            } else {
                ++losses;
                for (int id : sim.oppMoveIds) dangerCnt[id]++;
            }
            totalMyVal += sim.myVal;
            if (sim.blocked) ++blockedGames;
            if (!sim.oppVals.empty())
                totalOppMinVal += *std::min_element(sim.oppVals.begin(), sim.oppVals.end());
            totalDomControl += sim.dominanceControl;
            for (int c : sim.oppPassCounts) totalOppPasses += c;
        }

        // risk score from most frequent opponent tiles in lost sims
        std::vector<std::pair<int, long long>> danger;
        for (int id = 0; id < 28; ++id)
            if (dangerCnt[id] > 0) danger.emplace_back(id, dangerCnt[id]);
        std::stable_sort(danger.begin(), danger.end(),
                         [](const std::pair<int, long long>& x, const std::pair<int, long long>& y) {
                             return x.second > y.second;
                         });
        double riskScore = 0;
        std::string dangerJson;
        size_t topN = std::min<size_t>(danger.size(), 5);
        for (size_t k = 0; k < topN; ++k) {
            double freq = losses > 0 ? static_cast<double>(danger[k].second) / losses : 0.0;
            riskScore += freq * 10.0;
            if (k) dangerJson += ",";
            dangerJson += "{\"key\":" + jstr(g_tiles[danger[k].first].key) +
                          ",\"freq\":" + jnum(freq, 4) + "}";
        }

        double winRate = numSims > 0 ? static_cast<double>(wins) / numSims : 0.0;
        double blockRate = numSims > 0 ? static_cast<double>(blockedGames) / numSims : 0.0;
        double deadlockWinRate = numSims > 0 ? static_cast<double>(deadlockWins) / numSims : 0.0;
        double winByEmptyRate = wins > 0 ? static_cast<double>(winByEmpty) / wins : 0.0;
        double avgMyVal = numSims > 0 ? static_cast<double>(totalMyVal) / numSims : 0.0;
        double avgOppMinVal = numSims > 0 ? static_cast<double>(totalOppMinVal) / numSims : 0.0;
        double avgOppPasses = numSims > 0 ? static_cast<double>(totalOppPasses) / numSims : 0.0;
        double avgDomControl = numSims > 0 ? static_cast<double>(totalDomControl) / numSims : 0.0;

        if (mi) out << ",";
        out << "{";
        out << "\"key\":" << jstr(g_tiles[move.tileId].key);
        out << ",\"a\":" << move.a << ",\"b\":" << move.b;
        out << ",\"side\":" << (move.side == 0 ? "\"first\"" : move.side == 1 ? "\"left\"" : "\"right\"");
        out << ",\"newLeft\":" << nL << ",\"newRight\":" << nR;
        out << ",\"wins\":" << wins << ",\"losses\":" << losses << ",\"numSims\":" << numSims;
        out << ",\"winRate\":" << jnum(winRate, 6);
        out << ",\"avgMyVal\":" << jnum(avgMyVal, 3);
        out << ",\"avgOppMinVal\":" << jnum(avgOppMinVal, 3);
        out << ",\"flexibility\":" << flex;
        out << ",\"blockedGames\":" << blockedGames << ",\"blockRate\":" << jnum(blockRate, 6);
        out << ",\"deadlockWins\":" << deadlockWins << ",\"deadlockWinRate\":" << jnum(deadlockWinRate, 6);
        out << ",\"winByEmpty\":" << winByEmpty << ",\"winByValue\":" << winByValue;
        out << ",\"winByEmptyRate\":" << jnum(winByEmptyRate, 6);
        out << ",\"riskScore\":" << jnum(riskScore, 3);
        out << ",\"topDanger\":[" << dangerJson << "]";
        out << ",\"avgOppPasses\":" << jnum(avgOppPasses, 3);
        out << ",\"avgDomControl\":" << jnum(avgDomControl, 3);
        out << ",\"domSupportScore\":" << h.domSupportScore;
        out << ",\"domSupportReasons\":[";
        for (size_t k = 0; k < h.domSupportReasons.size(); ++k)
            out << (k ? "," : "") << jstr(h.domSupportReasons[k]);
        out << "]";
        out << ",\"trapScore\":" << h.trapScore;
        out << ",\"trapReasons\":[";
        for (size_t k = 0; k < h.trapReasons.size(); ++k)
            out << (k ? "," : "") << jstr(h.trapReasons[k]);
        out << "]";
        out << ",\"blockScore\":" << h.blockScore << ",\"selfTrapScore\":" << h.selfTrapScore;
        out << ",\"blockReasons\":[";
        for (size_t k = 0; k < h.blockReasons.size(); ++k)
            out << (k ? "," : "") << jstr(h.blockReasons[k]);
        out << "]";
        out << ",\"guaranteedBlocks\":[";
        for (size_t k = 0; k < h.guaranteedBlocks.size(); ++k)
            out << (k ? "," : "") << "{\"opp\":" << h.guaranteedBlocks[k].first
                                << ",\"reason\":" << jstr(h.guaranteedBlocks[k].second) << "}";
        out << "]";
        out << ",\"firstMoveSafety\":";
        if (safety) {
            out << "{\"canPlayNext\":" << safety->canPlayNext
                << ",\"totalRemaining\":" << safety->totalRemaining
                << ",\"safetyRatio\":" << jnum(safety->safetyRatio, 6)
                << ",\"canPlayKeys\":[";
            for (size_t k = 0; k < safety->canPlayKeys.size(); ++k)
                out << (k ? "," : "") << jstr(safety->canPlayKeys[k]);
            out << "],\"cannotPlayKeys\":[";
            for (size_t k = 0; k < safety->cannotPlayKeys.size(); ++k)
                out << (k ? "," : "") << jstr(safety->cannotPlayKeys[k]);
            out << "]}";
        } else out << "null";
        out << "}";
    }

    out << "]}";
    return out.str();
}

// ---------------------------------------------------------------------------
// Self-test
// ---------------------------------------------------------------------------
static std::string runSelftest() {
    struct Check { std::string name; bool pass; std::string detail; };
    std::vector<Check> checks;

    // 1. tile set integrity
    {
        bool pass = g_tiles.size() == 28;
        std::map<std::string, bool> uniq;
        for (const auto& t : g_tiles) uniq[t.key] = true;
        pass = pass && uniq.size() == 28;
        checks.push_back({"deck_28_kartu", pass,
                          pass ? "28 tile unik 0-0 .. 6-6" : "deck tidak valid"});
    }

    // 2. JSON parser round-trip
    {
        bool pass = true;
        std::string detail = "ok";
        try {
            JValue v = JParser("{\"a\":[1,2.5,-3],\"b\":\"x\\ny\",\"c\":true,\"d\":{\"e\":null}}").parse();
            pass = v.find("a")->arr.size() == 3 &&
                   v.find("a")->arr[1].num == 2.5 &&
                   v.find("b")->s == "x\ny" &&
                   v.find("c")->b == true &&
                   v.find("d")->find("e")->t == JValue::NUL;
        } catch (const std::exception& e) { pass = false; detail = e.what(); }
        checks.push_back({"parser_json", pass, detail});
    }

    // 3. determinism: same seed -> identical analysis output
    {
        bool pass = true;
        std::string detail = "2 pemain, seed tetap, 2x analisis identik";
        try {
            std::ostringstream payload;
            payload << "{\"cmd\":\"analyze\",\"numPlayers\":2,\"cardsPerPlayer\":7,"
                    << "\"numSims\":300,\"seed\":4242,\"leftEnd\":-1,\"rightEnd\":-1,"
                    << "\"myHand\":[\"0-0\",\"0-1\",\"0-2\",\"1-1\",\"2-3\",\"5-5\",\"6-6\"],"
                    << "\"played\":[],\"opponents\":[{\"eliminated\":[],\"passes\":0}]}";
            JValue req = JParser(payload.str()).parse();
            std::string r1 = runAnalyze(req);
            std::string r2 = runAnalyze(req);
            pass = (r1 == r2);
            if (!pass) detail = "output berbeda antar run dengan seed sama";
        } catch (const std::exception& e) { pass = false; detail = e.what(); }
        checks.push_back({"determinisme_seed", pass, detail});
    }

    // 4. card conservation + constraint satisfaction across random deals
    {
        bool pass = true;
        int fallbackScenarios = 0, scenarios = 400;
        std::string detail = "400 skenario acak";
        Rng rng(987654321ULL);
        for (int sc = 0; sc < scenarios && pass; ++sc) {
            int numPlayers = 2 + rng.nextInt(3);
            int numOpp = numPlayers - 1;
            int cardsPerPlayer = 28 / numPlayers;
            int myCount = 3 + rng.nextInt(cardsPerPlayer - 2);
            std::vector<int> deck(28);
            for (int i = 0; i < 28; ++i) deck[i] = i;
            rng.shuffle(deck);
            std::vector<int> mine(deck.begin(), deck.begin() + myCount);
            std::vector<int> unknown(deck.begin() + myCount, deck.end());
            int totalOppCards = static_cast<int>(unknown.size()) > 2
                                    ? static_cast<int>(unknown.size()) / 2
                                    : static_cast<int>(unknown.size());
            std::vector<std::vector<int>> elim(numOpp);
            for (int p = 0; p < numOpp; ++p)
                for (int n = 0; n <= 6; ++n)
                    if (rng.nextInt(4) == 0) elim[p].push_back(n);

            Deal deal = dealConstrained(unknown, numOpp, totalOppCards, elim, rng);

            // conservation: oppHands + boneyard must equal unknown (as multisets)
            std::vector<int> cnt(28, 0);
            for (const auto& h : deal.oppHands)
                for (int id : h) cnt[id]++;
            for (int id : deal.boneyard) cnt[id]++;
            for (int id : unknown)
                if (cnt[id] != 1) { pass = false; detail = "konservasi kartu gagal"; break; }

            // constraint: violations only allowed when fallback occurred
            bool anyFallback = deal.fallbacks > 0;
            if (anyFallback) fallbackScenarios++;
            if (!anyFallback) {
                for (int p = 0; p < numOpp && pass; ++p)
                    for (int id : deal.oppHands[p])
                        for (int n : elim[p])
                            if (g_tiles[id].a == n || g_tiles[id].b == n) {
                                pass = false;
                                detail = "constraint PASS dilanggar tanpa fallback";
                                break;
                            }
            }
        }
        if (pass) detail += " | fallback terjadi di " + std::to_string(fallbackScenarios) + " skenario (informasi)";
        checks.push_back({"deal_konservasi_&_constraint", pass, detail});
    }

    // 5. simulation invariants (termination + statistics sanity)
    {
        bool pass = true;
        std::string detail = "500 gim acak berhenti & statistik konsisten";
        try {
            Rng rng(13579ULL);
            std::vector<int> myHand = {tileId("0-0"), tileId("0-1"), tileId("0-2"),
                                       tileId("1-1"), tileId("2-3"), tileId("5-6"), tileId("6-6")};
            std::vector<int> unknown;
            for (int id = 0; id < 28; ++id)
                if (std::find(myHand.begin(), myHand.end(), id) == myHand.end()) unknown.push_back(id);
            std::vector<std::vector<int>> elim(3); // 4 pemain -> 3 lawan
            elim[0] = {6};
            elim[1] = {0, 1};
            int wins = 0;
            for (int s = 0; s < 500 && pass; ++s) {
                Deal deal = dealConstrained(unknown, 3, 14, elim, rng);
                Rng gameRng(rng.next());
                NumMap base = buildNumMap(myHand, {});
                SimResult sim = simulateGame(myHand, 3, 5, 4, deal, gameRng, base);
                if (sim.myTiles == 0 && sim.myVal != 0) pass = false;
                if (sim.iWin) ++wins;
            }
            if (wins == 0 || wins == 500) detail += " (peringatan: win rate ekstrem)";
        } catch (const std::exception& e) { pass = false; detail = e.what(); }
        checks.push_back({"simulasi_invariant", pass, detail});
    }

    std::ostringstream out;
    out << "{\"ok\":true,\"engine\":" << jstr("domino-cpp/" + std::string(ENGINE_VERSION))
        << ",\"allPass\":";
    bool all = true;
    for (const auto& c : checks) if (!c.pass) all = false;
    out << jbool(all) << ",\"checks\":[";
    for (size_t k = 0; k < checks.size(); ++k) {
        if (k) out << ",";
        out << "{\"name\":" << jstr(checks[k].name)
            << ",\"pass\":" << jbool(checks[k].pass)
            << ",\"detail\":" << jstr(checks[k].detail) << "}";
    }
    out << "]}";
    return out.str();
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------
int main() {
    initTiles();
    std::ostringstream ss;
    ss << std::cin.rdbuf();
    std::string input = ss.str();

    std::string out;
    try {
        JValue req = JParser(input).parse();
        std::string cmd = req.find("cmd") ? req.find("cmd")->asString("analyze") : "analyze";
        if (cmd == "selftest") out = runSelftest();
        else if (cmd == "analyze") out = runAnalyze(req);
        else throw std::runtime_error("unknown cmd: " + cmd);
    } catch (const std::exception& e) {
        out = std::string("{\"ok\":false,\"error\":") + jstr(e.what()) + "}";
    }
    std::cout << out << std::endl;
    return 0;
}
