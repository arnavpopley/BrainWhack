"""Proof of Whack: a blockchain where mining means calling whack().

Each block's hash picks a phrase of words from the whack list. To mine the next block
a miner must call whack() until the file it writes contains that exact phrase.
The winning whack is stored in the block as its proof. Anyone can re-check it.

    python3 proof_of_whack.py              mine 6 blocks
    python3 proof_of_whack.py 10           mine 10 blocks
    python3 proof_of_whack.py verify       re-check every block in whackchain.json
    python3 proof_of_whack.py tamper       a goose edits history; watch verify catch it

The genesis block is anchored to the newest real Bitcoin block (via mempool.space), so
the first phrase can't be known until Bitcoin mines it. At the end we compare our
whacks per second with Bitcoin's live hashrate. It goes badly for us.
"""
import hashlib
import json
import sys
import time
import urllib.request

from whack import WORDS, whack

CHAIN_FILE = "whackchain.json"
MINERS = ["Duck Pool", "Goose Syndicate", "Rubber Duck DAO"]
BIRDS = ["duck", "goose", "quack", "honk", "rubber"]
THINGS = ["pizza", "coffee", "wifi", "sleep", "semicolon", "prize", "demo"]


def block_hash(block):
    body = {k: block[k] for k in ("height", "prev", "txs", "miner", "proof", "difficulty")}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def target_phrase(prev_hash, difficulty):
    """The previous hash decides which words the next whack must contain."""
    n = int(prev_hash, 16)
    phrase = []
    for _ in range(difficulty):
        n, i = divmod(n, len(WORDS))
        phrase.append(WORDS[i])
    return phrase


def contains(words, phrase):
    k = len(phrase)
    return any(words[i:i + k] == phrase for i in range(len(words) - k + 1))


def transactions():
    """Transactions are written by whack() too."""
    words = whack()
    birds = list(dict.fromkeys(w for w in words if w in BIRDS))
    birds = birds if len(birds) >= 2 else ["duck", "goose"]
    things = [w for w in words if w in THINGS] or ["pizza"]
    txs = []
    for i in range(min(3, len(words) // 15 + 1)):
        a, b = birds[i % len(birds)], birds[(i + 1) % len(birds)]
        txs.append(f"{a} pays {b} {len(words) % 9 + 1} QUACK for {things[i % len(things)]}")
    return txs


MEMPOOL = "https://mempool.space/api"


def mempool(path):
    req = urllib.request.Request(MEMPOOL + path, headers={"User-Agent": "proof-of-whack"})
    with urllib.request.urlopen(req, timeout=6) as r:
        return r.read().decode()


def genesis():
    try:
        height = int(mempool("/blocks/tip/height"))
        btc_hash = mempool(f"/block-height/{height}")
        txs = [f"anchored to Bitcoin block {height}", "in the beginning there was a duck"]
        print(f"Genesis anchored to Bitcoin block {height}: {btc_hash}")
    except OSError:
        height, btc_hash = None, "0" * 64
        txs = ["offline genesis: in the beginning there was a duck"]
        print("Couldn't reach mempool.space, so the genesis block is unanchored")
    block = {"height": 0, "prev": btc_hash, "txs": txs, "btc_height": height,
             "miner": "WHACK 26", "proof": ["whack"], "difficulty": 1}
    block["hash"] = block_hash(block)
    return block


def versus_bitcoin(whacks_per_sec):
    try:
        rate = json.loads(mempool("/v1/mining/hashrate/3d"))["currentHashrate"]
    except (OSError, KeyError, ValueError):
        return
    print(f"\nBitcoin network right now: {rate:.2e} hashes/sec")
    print(f"Proof of Whack network:    {whacks_per_sec:,.0f} whacks/sec")
    print(f"To catch up you'd need {rate / whacks_per_sec:.1e} laptops calling whack(). Bring ducks.")


def mine(chain, difficulty):
    prev = chain[-1]
    phrase = target_phrase(prev["hash"], difficulty)
    txs = transactions()
    print(f"\nBlock {prev['height'] + 1}: the chain demands \"{' '.join(phrase)}\"")
    for tx in txs:
        print(f"  tx: {tx}")
    start, whacks = time.time(), 0
    while True:
        miner = MINERS[whacks % len(MINERS)]
        words = whack()
        whacks += 1
        if whacks % 2000 == 0:
            rate = whacks / (time.time() - start)
            print(f"  ...{whacks} whacks, {rate:,.0f} whacks/sec", end="\r")
        if contains(words, phrase):
            break
    elapsed = time.time() - start
    i = next(i for i in range(len(words)) if words[i:i + difficulty] == phrase)
    print(f"\r{' ' * 60}\r  {miner} found it after {whacks:,} whacks ({elapsed:.2f}s, {whacks / max(elapsed, 1e-9):,.0f} whacks/sec)")
    snippet = words[max(0, i - 3):i] + [w.upper() for w in phrase] + words[i + difficulty:i + difficulty + 3]
    print(f"  proof: ...{' '.join(snippet)}...")
    block = {"height": prev["height"] + 1, "prev": prev["hash"], "txs": txs + [f"reward: 1 QUACK to {miner}"],
             "miner": miner, "proof": words, "difficulty": difficulty}
    block["hash"] = block_hash(block)
    print(f"  hash: {block['hash'][:32]}...")
    return block, elapsed, whacks


def verify(chain):
    ok = True
    anchor = chain[0].get("btc_height")
    if anchor is not None:
        try:
            real = mempool(f"/block-height/{anchor}")
            good = real == chain[0]["prev"]
            print(f"  [{'OK  ' if good else 'FAIL'}] genesis anchor matches Bitcoin block {anchor}")
            ok = good
        except OSError:
            print("  [????] couldn't reach mempool.space to check the Bitcoin anchor")
    for prev, block in zip(chain, chain[1:]):
        problems = []
        if block["prev"] != prev["hash"]:
            problems.append("prev hash does not match")
        if block_hash(block) != block["hash"]:
            problems.append("block contents were changed after mining")
        phrase = target_phrase(prev["hash"], block["difficulty"])
        if not contains(block["proof"], phrase):
            problems.append(f"proof whack does not contain \"{' '.join(phrase)}\"")
        status = "OK  " if not problems else "FAIL"
        print(f"  [{status}] block {block['height']} mined by {block['miner']}" + (f": {'; '.join(problems)}" if problems else ""))
        ok = ok and not problems
    print("\nChain is valid. In whack we trust." if ok else "\nChain is INVALID. A goose has been tampering.")
    return ok


def load():
    with open(CHAIN_FILE) as f:
        return json.load(f)


def save(chain):
    with open(CHAIN_FILE, "w") as f:
        json.dump(chain, f, indent=1)


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "6"
    if arg == "verify":
        verify(load())
        return
    if arg == "tamper":
        chain = load()
        victim = chain[min(2, len(chain) - 1)]
        victim["txs"][0] = "goose pays goose 1000000 QUACK for nothing"
        save(chain)
        print(f"A goose rewrote block {victim['height']}: \"{victim['txs'][0]}\"\n")
        verify(chain)
        return
    print("Proof of Whack. Difficulty = how many words in a row the whack must contain.")
    chain, difficulty = [genesis()], 1
    total_whacks, total_time = 0, 0.0
    for _ in range(int(arg)):
        block, elapsed, whacks = mine(chain, difficulty)
        total_whacks, total_time = total_whacks + whacks, total_time + elapsed
        chain.append(block)
        # difficulty adjustment, like Bitcoin but sillier: aim for about one second per block
        if elapsed < 0.5 and difficulty < 4:
            difficulty += 1
            print(f"  too easy! difficulty rises to {difficulty}")
        elif elapsed > 5 and difficulty > 1:
            difficulty -= 1
            print(f"  too slow! difficulty drops to {difficulty}")
    save(chain)
    versus_bitcoin(total_whacks / max(total_time, 1e-9))
    print(f"\nSaved {len(chain)} blocks to {CHAIN_FILE}. Now try: python3 proof_of_whack.py verify")


if __name__ == "__main__":
    main()
