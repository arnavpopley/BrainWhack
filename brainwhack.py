"""BrainWhack: every whack() output is a program, and whack() is the only dice in the box.

The 42 words are the opcodes of a tiny stack machine that works on bytes (0-255).
The breeder evolves programs that print a target. Every program it starts from, every
mutation it makes and every random choice it takes comes from calling whack().
This file never imports Python's random module.

    python3 brainwhack.py               whack() once, then run the program it wrote
    python3 brainwhack.py evolve HONK   breed a program that prints HONK, live in the terminal
    python3 brainwhack.py evolve        let whack() choose what to breed
    python3 brainwhack.py trace FILE    step through a program one instruction at a time
    python3 brainwhack.py run FILE      run any file of BrainWhack words (try: run whack)
    python3 brainwhack.py census        run 1,000 wild whack() programs and see what lives there
    python3 brainwhack.py ops           the instruction set
    python3 whack_lab.py               the breeder, visualised in the browser
"""
import os
import re
import sys
import time

from whack import WORDS, whack

MAX_STEPS = 5000    # random programs loop forever a lot; this keeps it harmless
BREED_STEPS = 600   # tighter limit while breeding: programs that loop are wasted effort
INDEX = {w: i for i, w in enumerate(WORDS)}
LITERALS = {"null": 0, "one": 1, "pizza": 8, "midnight": 12, "capital": 65, "prize": 100}

DOCS = {
    "null": "push 0", "one": "push 1", "pizza": "push 8 (slices)", "midnight": "push 12",
    "capital": "push 65 (capital A)", "prize": "push 100",
    "coffee": "top + 1", "sleep": "top - 1", "merge": "pop b, a; push a + b",
    "conflict": "pop b, a; push a - b", "overflow": "pop b, a; push a * b (wraps at 256)",
    "brevan": "top * 2", "howard": "top / 2", "bloomberg": "push the sum of the whole stack",
    "push": "duplicate top", "commit": "drop top", "bug": "swap the top two",
    "pointer": "rotate the third item to the top", "stack": "push the stack depth",
    "honk": "print top as a character (geese honk and stay)",
    "quack": "print top as a character, then pop it (ducks quack and leave)",
    "io": "print top as a number", "deploy": "ship it: print the whole stack, then clear it",
    "duck": "loop start", "goose": "if top isn't 0, fly back to the matching duck",
    "incident": "if top is 0, skip the next word", "wifi": "skip the next word (packet dropped)",
    "segfault": "halt: Segmentation fault (core dumped)",
    "rubber": "rubber duck debugging: print what's on the stack",
    "whack": "no-op", "hack": "no-op", "feature": "no-op (it's not a bug)", "demo": "no-op (demo mode)",
    "pitch": "no-op", "semicolon": "no-op (optional, like in JavaScript)", "prod": "no-op (works on my machine)",
}
NOOPS = ["whack", "hack", "feature", "demo", "pitch", "semicolon", "prod",
         "warwick", "oculus", "compsoc", "marshall", "wace", "netcraft"]
for _w in NOOPS:
    DOCS.setdefault(_w, "no-op (sponsor slot: does nothing, looks great on the slide)")

FAMILIES = {
    "literal": ["null", "one", "pizza", "midnight", "capital", "prize"],
    "math": ["coffee", "sleep", "merge", "conflict", "overflow", "brevan", "howard", "bloomberg"],
    "stack": ["push", "commit", "bug", "pointer", "stack"],
    "output": ["honk", "quack", "io", "deploy"],
    "control": ["duck", "goose", "incident", "wifi", "segfault"],
    "debug": ["rubber"],
    "noop": NOOPS,
}
FAMILY = {w: f for f, ws in FAMILIES.items() for w in ws}
ENDINGS = {"exit": "exited cleanly", "segfault": "Segmentation fault (core dumped)",
           "timeout": "still running after 5,000 steps (infinite loop, very relatable)"}


# ---------------------------------------------------------------- the machine

def char(c):
    return chr(c) if 32 <= c < 127 else "·"


def show(b):
    return "".join(char(c) for c in b)


def match_loops(prog):
    """duck ... goose works like brackets. Unmatched ones are no-ops."""
    pairs, open_ducks = {}, []
    for i, w in enumerate(prog):
        if w == "duck":
            open_ducks.append(i)
        elif w == "goose" and open_ducks:
            pairs[i] = open_ducks.pop()
    return pairs


def run(prog, max_steps=MAX_STEPS, trace=None, trace_limit=10_000):
    """Runs a program. Returns (output bytes, ending, steps). Pass a list as trace to record each step."""
    stack, out = [], bytearray()
    jumps = match_loops(prog)
    pc = steps = 0

    def pop():
        return stack.pop() if stack else 0  # an empty stack yields 0, so random code keeps going

    def push(v):
        stack.append(v % 256)

    while pc < len(prog):
        steps += 1
        if steps > max_steps:
            return bytes(out), "timeout", max_steps
        w = prog[pc]
        nxt, note = pc + 1, ""
        if w in LITERALS:
            push(LITERALS[w])
        elif w == "coffee":
            push(pop() + 1)
        elif w == "sleep":
            push(pop() - 1)
        elif w == "brevan":
            push(pop() * 2)
        elif w == "howard":
            push(pop() // 2)
        elif w in ("merge", "conflict", "overflow"):
            b, a = pop(), pop()
            push(a + b if w == "merge" else a - b if w == "conflict" else a * b)
        elif w == "bloomberg":
            push(sum(stack))
        elif w == "push":
            v = pop()
            push(v)
            push(v)
        elif w == "commit":
            pop()
        elif w == "bug":
            b, a = pop(), pop()
            push(b)
            push(a)
        elif w == "pointer":
            if len(stack) >= 3:
                stack.append(stack.pop(-3))
        elif w == "stack":
            push(len(stack))
        elif w == "honk":
            out.append(stack[-1] if stack else 0)
            note = "prints " + repr(char(out[-1]))
        elif w == "quack":
            out.append(pop())
            note = "prints " + repr(char(out[-1])) + " and pops it"
        elif w == "io":
            out.extend(str(stack[-1] if stack else 0).encode())
        elif w == "deploy":
            out.extend(stack)
            stack.clear()
        elif w == "goose":
            if pc in jumps and stack and stack[-1] != 0:
                nxt, note = jumps[pc] + 1, "top isn't 0: fly back to the duck"
        elif w == "incident":
            if not stack or stack[-1] == 0:
                nxt, note = pc + 2, "top is 0: skip " + (prog[pc + 1] if pc + 1 < len(prog) else "nothing")
        elif w == "wifi":
            nxt, note = pc + 2, "packet dropped: skip " + (prog[pc + 1] if pc + 1 < len(prog) else "nothing")
        elif w == "rubber":
            out.extend(f"<rubber duck sees {stack[-5:]}>".encode())
        if trace is not None and len(trace) < trace_limit:
            trace.append({"pc": pc, "w": w, "stack": stack[-10:], "out": list(out),
                          "note": "Segmentation fault (core dumped)" if w == "segfault" else note})
        if w == "segfault":
            return bytes(out), "segfault", steps
        pc = nxt
    return bytes(out), "exit", steps


def load(path):
    with open(path, encoding="utf-8") as f:
        return [w for line in f if not line.lstrip().startswith("#") for w in line.split()]


# ---------------------------------------------------------------- whack() as the only dice

class WhackRandom:
    """All of the breeder's randomness. Each word whack() writes is a digit in base 42."""

    def __init__(self):
        self.digits, self.last = [], []
        self.gene_calls = self.dice_calls = 0

    @property
    def calls(self):
        return self.gene_calls + self.dice_calls

    def genes(self):
        """A fresh whack(), used as genetic material."""
        self.gene_calls += 1
        self.last = whack()
        return self.last

    def digit(self):
        if not self.digits:
            self.dice_calls += 1
            self.last = whack()
            self.digits = [INDEX[w] for w in self.last]
        return self.digits.pop()

    def below(self, n):
        """A fair integer in [0, n), built from base-42 digits with rejection sampling."""
        if n <= 1:
            return 0
        span, k = 42, 1
        while span < n:
            span, k = span * 42, k + 1
        while True:
            v = 0
            for _ in range(k):
                v = v * 42 + self.digit()
            if v < span - span % n:
                return v % n

    def choice(self, seq):
        return seq[self.below(len(seq))]


def whack_target(rng):
    """Let whack() choose what to breed: the first 2-5 letter word of a fresh whack()."""
    while True:
        for w in rng.genes():
            if 2 <= len(w) <= 5:
                return w.upper()


# ---------------------------------------------------------------- the breeder

def fitness(out, target):
    """A staircase: 1,000 points per correct leading letter, plus up to 256 for how close
    the next letter is. Once every letter is right, extra output costs points."""
    n = 0
    while n < len(target) and n < len(out) and out[n] == target[n]:
        n += 1
    if n == len(target):
        return 1000 * n + 256 - 40 * (len(out) - n)
    return 1000 * n + (256 - abs(out[n] - target[n]) if n < len(out) else 0)


def mutate(prog, other, rng):
    """Four kinds of mutation. whack() picks which one, where, and supplies any new words."""
    child = list(prog)
    kind = rng.below(4)
    if kind == 0:    # splice: a few words from a fresh whack() replace a few words here
        donor = rng.genes()
        i = rng.below(len(child) + 1)
        j = min(len(child), i + rng.below(3))
        k = rng.below(len(donor))
        child[i:j] = donor[k:k + rng.below(3)]
    elif kind == 1 and child:    # point mutation: one word swapped for one from a fresh whack()
        child[rng.below(len(child))] = rng.choice(rng.genes())
    elif kind == 2:    # crossover: the front of one parent, the back of another, cut at the same place
        cut = rng.below(min(len(child), len(other)) + 1)
        child = child[:cut] + other[cut:]
    elif child:    # deletion
        i = rng.below(len(child))
        del child[i:i + 1 + rng.below(2)]
    return child[:120]


def prune(prog, target):
    """Drops every word the program still works without. Returns (pruned, kept indices)."""
    keep = list(range(len(prog)))
    i = 0
    while i < len(keep):
        trial = keep[:i] + keep[i + 1:]
        out, ending, _ = run([prog[k] for k in trial])
        if out == target and ending != "timeout":
            keep = trial
        else:
            i += 1
    return [prog[k] for k in keep], keep


def evolve(target_text, rng=None, pop_size=40, elite=10, stall_limit=700, time_limit=60):
    """Breeds a program that prints target_text. Yields an event every generation."""
    rng = rng or WhackRandom()
    target = target_text.encode("latin-1")
    cache = {}

    def judge(p):
        key = " ".join(p)
        hit = cache.get(key)
        if hit is None:
            out, ending, _ = run(p, BREED_STEPS)
            hit = cache[key] = (fitness(out, target), ending != "timeout", out, ending)
        return hit

    start = time.time()
    population = [rng.genes() for _ in range(pop_size)]
    gen = restarts = stalled = 0
    record = None
    while True:
        gen += 1
        if len(cache) > 300_000:
            cache.clear()
        # fittest first; programs that halt beat ones that loop; whack() breaks ties so the flock can drift
        ranked = sorted(population, key=lambda p: (*judge(p)[:2], rng.below(1764)), reverse=True)
        champ = ranked[0]
        score, _, out, ending = judge(champ)
        improved = record is None or score > record
        record, stalled = (score, 0) if improved else (record, stalled + 1)
        base = {"gen": gen, "calls": rng.calls, "genes": rng.gene_calls, "dice": rng.dice_calls,
                "restarts": restarts, "elapsed": time.time() - start, "target_text": target_text}
        if out == target and ending != "timeout":
            pruned, keep = prune(champ, target)
            trace = []
            _, ending, steps = run(pruned, trace=trace)
            yield {**base, "type": "done", "before": champ, "keep": keep, "program": pruned,
                   "trace": trace, "ending": ending, "steps": steps}
            return
        if base["elapsed"] > time_limit:    # hard cap: give up after 60 seconds
            yield {**base, "type": "gaveup", "out": out}
            return
        yield {**base, "type": "gen", "score": score, "max": 1000 * len(target) + 256, "out": out,
               "target": target, "champ": champ, "ranked": ranked, "rain": rng.last, "improved": improved}
        if stalled > stall_limit:    # stuck: the goose scatters the flock and breeding starts again
            restarts += 1
            yield {**base, "type": "restart", "restarts": restarts, "stuck_on": out}
            population, record, stalled = [rng.genes() for _ in range(pop_size)], None, 0
            continue
        parents = ranked[:elite]
        population = parents + [mutate(rng.choice(parents), rng.choice(parents), rng)
                                for _ in range(pop_size - elite)]


# ---------------------------------------------------------------- terminal views

TTY = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
COLOR = {"literal": 220, "math": 45, "stack": 141, "output": 204, "control": 84, "debug": 226, "noop": 240}


def ansi(text, code):
    return f"\x1b[{code}m{text}\x1b[0m" if TTY else text


def paint(w, text=None):
    color = 196 if w == "segfault" else COLOR[FAMILY[w]]
    return ansi(w if text is None else text, f"38;5;{color}")


def bold(t):
    return ansi(t, "1")


def dim(t):
    return ansi(t, "2")


def green(t):
    return ansi(t, "1;38;5;84")


def wrap_words(words, width=96, indent="  "):
    lines, line, n = [], [], 0
    for w in words:
        if line and n + len(w) + 1 > width:
            lines.append(indent + " ".join(line))
            line, n = [], 0
        line.append(paint(w))
        n += len(w) + 1
    if line:
        lines.append(indent + " ".join(line))
    return lines


def dashboard(ev, note=""):
    size = os.get_terminal_size() if TTY else os.terminal_size((100, 40))
    width = min(size.columns, 120)
    tgt, out = ev["target"], ev["out"]
    pct = max(ev["score"], 0) / ev["max"]
    fill = round(40 * pct)
    want, got, off = [], [], []
    for i, t in enumerate(tgt):
        want.append(char(t).ljust(5))
        if i < len(out):
            d = abs(out[i] - t)
            got.append((green(char(out[i])) if d == 0 else char(out[i])) + "    ")
            off.append(green("ok   ") if d == 0 else str(d).ljust(5))
        else:
            got.append(dim("_    "))
            off.append(dim("?    "))
    extra = len(out) - len(tgt)
    calls = f"{ev['calls']:,}"
    lines = [
        bold("BRAINWHACK BREEDER") + "   breeding a program that prints " + bold(repr(ev["target_text"])),
        "",
        f"  generation {ev['gen']:,}    restarts {ev['restarts']}    whack() calls " + bold(calls)
        + dim(f"  ({ev['genes']:,} for genes, {ev['dice']:,} for dice)"),
        "  fitness    " + green("█" * fill) + dim("░" * (40 - fill)) + f" {pct:.1%}",
        "",
        "  target     " + "".join(want),
        "  best       " + "".join(got) + (dim(f"(+{extra} extra)") if extra > 0 else ""),
        "  off by     " + "".join(off),
        "  " + dim(note),
        f"  champion program ({len(ev['champ'])} words)",
        *wrap_words(ev["champ"], width - 8, "    "),
        "",
        "  gene pool: one row per program, one block per word, fittest first",
    ]
    rows = max(0, min(14, size.lines - len(lines) - 2))
    lines += ["    " + "".join(paint(w, "█") for w in p[:width - 8]) for p in ev["ranked"][:rows]]
    return "\x1b[H" + "\n".join(line + "\x1b[K" for line in lines) + "\x1b[J"


def save(ev):
    name = "bred_" + re.sub(r"[^A-Za-z0-9]", "_", ev["target_text"]) + ".bw"
    with open(name, "w", encoding="utf-8") as f:
        f.write(f"# BrainWhack program bred to print {ev['target_text']!r}\n")
        f.write(f"# {ev['gen']:,} generations, {ev['calls']:,} calls to whack() ({ev['genes']:,} genes, "
                f"{ev['dice']:,} dice), {ev['restarts']} restarts, {ev['elapsed']:.1f}s\n")
        f.write(" ".join(ev["program"]) + "\n")
    return name


def breed_cli(target):
    rng = WhackRandom()
    if not target:
        target = whack_target(rng)
        print(f"whack() chose the target: {target}")
        time.sleep(1.5)
    target = "".join(c for c in target if 32 <= ord(c) < 127)[:8] or "HONK"
    last, note = 0.0, ""
    if TTY:
        sys.stdout.write("\x1b[?25l\x1b[2J")
    try:
        for ev in evolve(target, rng):
            if ev["type"] == "restart":
                note = f"gen {ev['gen']:,}: stuck on {show(ev['stuck_on'])[:30]!r}. Honk! The goose scatters the flock."
                if not TTY:
                    print(note)
            elif ev["type"] == "gen" and time.time() - last > 0.08:
                last = time.time()
                if TTY:
                    sys.stdout.write(dashboard(ev, note))
                    sys.stdout.flush()
                elif ev["gen"] % 250 == 0:
                    print(f"gen {ev['gen']:,}  whack() calls {ev['calls']:,}  best {show(ev['out'])[:30]!r}")
    finally:
        if TTY:
            sys.stdout.write("\x1b[?25h\x1b[2J\x1b[H")
    if ev["type"] == "gaveup":
        print(f"Gave up after {ev['elapsed']:.0f}s and {ev['gen']:,} generations. Best output: {show(ev['out'])!r}")
        return
    out = bytes(ev["trace"][-1]["out"]) if ev["trace"] else b""
    print(bold(f"Bred a program that prints {target!r}") + f" in {ev['gen']:,} generations and {ev['elapsed']:.1f}s.")
    print(f"whack() was called {ev['calls']:,} times: {ev['genes']:,} for genetic material, {ev['dice']:,} for dice.\n")
    print(f"The champion had {len(ev['before'])} words. These {len(ev['program'])} are the ones that matter:\n")
    print("\n".join(wrap_words(ev["program"], 90, "  ")))
    print(f"\nOutput {show(out)!r}, then {ENDINGS[ev['ending']]} after {ev['steps']} steps.")
    name = save(ev)
    print(f"Saved to {name}. Step through it: python3 brainwhack.py trace {name}")


def trace_cli(path):
    prog = load(path)
    frames = []
    out, ending, steps = run(prog, trace=frames, trace_limit=200)
    print(dim(f"{'step':>4}  {'word':<10}{'stack (top on the right)':<28}{'output':<12}what happened"))
    for i, f in enumerate(frames, 1):
        word = paint(f["w"], f["w"].ljust(10))
        stack = " ".join(str(v) for v in f["stack"][-7:]).ljust(28)
        printed = repr(show(bytes(f["out"])))[:11].ljust(12)
        print(f"{i:>4}  {word}{stack}{printed}" + dim(f["note"] or DOCS[f["w"]]))
    if steps > len(frames):
        print(dim(f"  ... and {steps - len(frames):,} more steps"))
    print(f"\nOutput {show(out)!r}, then {ENDINGS[ending]}.")


def census(n=1000):
    endings = dict.fromkeys(ENDINGS, 0)
    spoke = worded = 0
    best, best_prog = b"", []
    start = time.time()
    for _ in range(n):
        prog = whack()
        out, ending, _ = run(prog)
        endings[ending] += 1
        spoke += bool(out)
        found = re.findall(rb"[A-Za-z]{2,}", out)
        if found:
            worded += 1
            longest = max(found, key=len)
            if len(longest) > len(best):
                best, best_prog = longest, prog
    print(bold(f"Census of {n:,} wild whack() programs") + dim(f"  ({time.time() - start:.1f}s)") + "\n")
    for label, k in [("died of a segfault", endings["segfault"]), ("looped forever", endings["timeout"]),
                     ("exited cleanly", endings["exit"]), ("printed anything at all", spoke),
                     ("printed 2+ letters in a row", worded)]:
        bar = round(30 * k / n)
        print(f"  {label:<28} " + green("█" * bar) + dim("░" * (30 - bar)) + f" {k / n:6.1%}")
    if best:
        said = best.decode()[:30] + ("..." if len(best) > 30 else "")
        print(f"\n  The most eloquent wild program said {said!r}. It was {len(best_prog)} words long.")
    print("\n  Nothing in the wild says HONK. Try: python3 brainwhack.py evolve HONK")


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else ""
    if cmd not in ("", "ops", "evolve", "census", "trace", "run"):
        print(__doc__)
        return
    if cmd in ("run", "trace") and (len(args) < 2 or not os.path.exists(args[1])):
        missing = f"No file called {args[1]!r}. " if len(args) > 1 else ""
        print(f"{missing}Usage: python3 brainwhack.py {cmd} FILE   (try: python3 brainwhack.py {cmd} bred_HONK.bw)")
        return
    if cmd == "ops":
        for fam, ws in FAMILIES.items():
            print(bold(fam))
            for w in ws:
                print(f"  {paint(w, w.ljust(10))} {DOCS[w]}")
    elif cmd == "evolve":
        breed_cli(args[1] if len(args) > 1 else None)
    elif cmd == "census":
        census(int(args[1]) if len(args) > 1 and args[1].isdigit() else 1000)
    elif cmd == "trace":
        trace_cli(args[1])
    else:
        if cmd == "run":
            prog = load(args[1])
            print(f"Running {args[1]} ({len(prog)} words)\n")
        else:
            whack()
            prog = load("whack")  # read the program back from the file whack() wrote
            print(f"whack() wrote a {len(prog)}-word program:\n")
        print("\n".join(wrap_words(prog)) + "\n")
        out, ending, steps = run(prog)
        print(f"Output:  {show(out)!r}")
        print(f"Ended:   {ENDINGS[ending]} after {steps:,} steps")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped. Honk.")
