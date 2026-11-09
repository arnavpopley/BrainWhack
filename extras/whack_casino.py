"""Whack Casino: a slot machine with honest, exactly computed odds.

Pull the lever and whack() writes its file. The reels scroll up through that file and
stop on its first three lines. A full whack (all 100 lines) doubles your win.
A whack shorter than 3 lines jams the machine and you lose.

PROVABLY FAIR: before each pull the machine commits to the *next* round of drand, the
League of Entropy's public randomness beacon (a new BLS-signed random value every 3s,
run by Cloudflare, Protocol Labs, universities and others). That value plus your lucky
phrase plus the pull number seeds Python's random module, then whack() is called.
Neither you nor the house can know the result in advance, and anyone can replay it.

    python3 whack_casino.py          play (Enter to pull, q to cash out)
    python3 whack_casino.py odds     the exact paytable, house edge included
    python3 whack_casino.py sim 5000 pull 5000 times and compare luck against the maths
    python3 whack_casino.py verify ROUND PHRASE NONCE   replay any pull from the beacon
"""
import hashlib
import itertools
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from fractions import Fraction

from whack import WORDS, whack

BIRDS = {"duck", "quack", "goose", "honk"}
TRINITY = {"pizza", "coffee", "sleep"}

# (name, payout per 1 credit bet, rule on the three reels). First matching rule wins.
PAYTABLE = [
    ("DUCK DUCK GOOSE", 2000, lambda r: r == ("duck", "duck", "goose")),
    ("Triple segfault: you found the bug", 1000, lambda r: r == ("segfault",) * 3),
    ("Three of a kind", 250, lambda r: r[0] == r[1] == r[2]),
    ("Hackathon trinity: pizza coffee sleep", 150, lambda r: set(r) == TRINITY),
    ("Full flock: three birds", 40, lambda r: set(r) <= BIRDS),
    ("Segfault: core dumped, no win", 0, lambda r: "segfault" in r),
    ("A pair", 5, lambda r: len(set(r)) == 2),
    ("Prize on the reels", 3, lambda r: "prize" in r),
    ("A bird: money back", 1, lambda r: bool(BIRDS & set(r))),
]
FULL_WHACK_MULTIPLIER = 2


def judge(reels):
    for name, pays, rule in PAYTABLE:
        if rule(tuple(reels)):
            return name, pays
    return "Nothing", 0


def exact_odds():
    """Walks all 42^3 reel results. whack() picks each word uniformly and the length
    uniformly from 1-100, so every probability here is exact, not estimated."""
    per_combo = Fraction(1, len(WORDS) ** 3)
    p_jam = Fraction(2, 100)                 # lengths 1 and 2
    p_full = Fraction(1, 100)                # length 100
    p_normal = 1 - p_jam - p_full
    probs = {name: Fraction(0) for name, _, _ in PAYTABLE}
    probs["Nothing"] = Fraction(0)
    for reels in itertools.product(WORDS, repeat=3):
        probs[judge(reels)[0]] += per_combo
    pays = {name: p for name, p, _ in PAYTABLE} | {"Nothing": 0}
    rtp = sum((p_normal + p_full * FULL_WHACK_MULTIPLIER) * probs[n] * pays[n] for n in probs)
    return probs, pays, p_jam, rtp


def print_odds():
    probs, pays, p_jam, rtp = exact_odds()
    print(f"{'outcome':<40}{'pays':>6}   {'chance (1 in N)':>16}")
    print(f"{'Jammed: whack wrote under 3 lines':<40}{0:>6}   {float(1 / p_jam):>16,.1f}")
    for name, p in probs.items():
        print(f"{name:<40}{pays[name]:>6}   {float(1 / (p * (1 - p_jam))):>16,.1f}")
    print(f"\nFull whack (100 lines) multiplies any win by {FULL_WHACK_MULTIPLIER}: 1 in 100")
    print(f"Return to player: {float(rtp):.4%}   House edge: {float(1 - rtp):.4%}")
    print(f"Exact RTP as a fraction: {rtp}")


DRAND = "https://api.drand.sh/52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971/public/"


def beacon(round_="latest"):
    req = urllib.request.Request(DRAND + str(round_), headers={"User-Agent": "whack-casino"})
    with urllib.request.urlopen(req, timeout=5) as r:
        data = json.load(r)
    return data["round"], data["randomness"]


def next_beacon():
    """Commit to a round that doesn't exist yet, then wait for the League of Entropy to publish it."""
    target = beacon()[0] + 1
    for _ in range(40):
        try:
            return beacon(target)
        except urllib.error.HTTPError:  # 425 Too Early: the future hasn't happened yet
            time.sleep(0.25)
    raise OSError("beacon is late")


def seeded_whack(randomness, phrase, nonce):
    seed = hashlib.sha256(f"{randomness}:{phrase}:{nonce}".encode()).hexdigest()
    random.seed(int(seed, 16))  # whack() uses the random module, so this fixes its output
    return whack()


def verify(round_, phrase, nonce):
    rnd, randomness = beacon(round_)
    print(f"drand quicknet round {rnd}: {randomness}")
    words, reels, name, pays = pull(seeded_whack(randomness, phrase, nonce))
    print(f"Replayed whack(): {len(words)} lines, reels {' | '.join(w.upper() for w in (reels or words))}")
    print(f"Result: {name}, pays {pays}")


def pull(words=None):
    words = whack() if words is None else words
    if len(words) < 3:
        return words, None, "JAMMED: whack only wrote %d line%s" % (len(words), "" if len(words) == 1 else "s"), 0
    name, pays = judge(words[:3])
    if pays and len(words) == 100:
        name, pays = f"{name} + FULL WHACK x{FULL_WHACK_MULTIPLIER}", pays * FULL_WHACK_MULTIPLIER
    return words, words[:3], name, pays


def spin(words):
    """The reels scroll up through the actual whack file and land on its top three lines."""
    padded = words + [""] * 3
    for start in range(max(0, len(words) - 3), -1, -1):
        window = padded[start:start + 3]
        print("\r  | " + " | ".join(f"{w.upper():^9}" for w in window) + " |", end="", flush=True)
        time.sleep(min(0.04, 1.2 / max(len(words), 1)))
    print()


def play():
    credits, nonce = 100, 0
    print("WHACK CASINO. 1 credit a pull. Enter to pull, q to cash out. (python3 whack_casino.py odds for the maths)")
    phrase = input("Pick a lucky phrase. It goes into every seed, so the house can't rig your pulls: ").strip() or "quack"
    print()
    while credits > 0:
        if input(f"[{credits} credits] pull? ").strip().lower() == "q":
            break
        credits -= 1
        nonce += 1
        print("  the League of Entropy is rolling the dice...", end="", flush=True)
        try:
            rnd, randomness = next_beacon()
            proof = f"verify: python3 whack_casino.py verify {rnd} \"{phrase}\" {nonce}"
        except OSError:
            randomness = os.urandom(32).hex()
            proof = "offline: this pull used local randomness and can't be verified"
        print("\r" + " " * 50 + "\r", end="")
        words, reels, name, pays = pull(seeded_whack(randomness, phrase, nonce))
        if reels:
            spin(words)
        credits += pays
        print(f"  {name}: " + (f"+{pays} credits" if pays else "no win") + f"   (whack wrote {len(words)} lines)")
        print(f"  {proof}\n")
    print(f"You leave with {credits} credits. The house thanks you. Honk.")


def simulate(n):
    probs, pays, p_jam, rtp = exact_odds()
    counts, paid = {}, 0
    for _ in range(n):
        words, reels, name, win = pull()
        key = "Jammed" if reels is None else name.split(" + ")[0]
        counts[key] = counts.get(key, 0) + 1
        paid += win
    print(f"{n:,} real pulls with whack()\n")
    print(f"{'outcome':<40}{'seen':>8}{'expected':>11}")
    print(f"{'Jammed':<40}{counts.get('Jammed', 0):>8}{float(p_jam * n):>11.1f}")
    for name, p in probs.items():
        print(f"{name:<40}{counts.get(name, 0):>8}{float(p * (1 - p_jam) * n):>11.1f}")
    print(f"\nYour RTP: {paid / n:.2%}   The maths says: {float(rtp):.2%}")
    print("(About a fifth of the RTP sits in jackpots you will rarely see, so short runs usually come in low.)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "play"
    if cmd == "odds":
        print_odds()
    elif cmd == "verify":
        verify(int(sys.argv[2]), sys.argv[3], int(sys.argv[4]))
    elif cmd == "sim":
        simulate(int(sys.argv[2]) if len(sys.argv) > 2 else 5000)
    else:
        play()
