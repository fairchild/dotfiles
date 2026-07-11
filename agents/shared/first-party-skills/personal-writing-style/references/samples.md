# Canonical writing samples

Samples of the voice this skill produces, organized by audience register. Use them as calibration anchors — especially when a request is ambiguous about register, length, or technical depth. These are reference points, not templates; the goal is to produce prose that would fit next to them, not to imitate their specific sentences.

Each sample sits in one register. When a task spans registers (e.g., a README with both peer and open-source-reader sections), blend the relevant samples rather than picking one.

---

## Peer / technical register

For README bodies, design docs, architecture explorations, and writeups aimed at engineers who share the author's context.

> A small Ruby library for background jobs that survive process crashes, machine reboots, and deploys without dropping work. It sits on top of Sidekiq — so the scheduling, retries, and dashboard you already know keep working — with a thin layer that checkpoints each step of a job to Redis as it runs. If the worker dies halfway through sending five emails, the job picks up at email four when the next worker claims it. The tradeoff is write amplification: every step writes a checkpoint, so jobs with many small operations will see Redis traffic roughly 2x what plain Sidekiq would produce. For the jobs this library is designed for — ones where losing work costs more than microseconds of latency — that's the right side of the trade.

---

## Short brief / three-beat

For capability requests, feature proposals, and compressed project descriptions. The shape is *what it is → how it works → why it matters in context.*

> I want a small tool that watches a folder for new markdown files, runs them through a linter, and drops a report next to each file with the issues found. The linter rules should be configurable via a yaml file in the folder, so I can have different rules per folder. The reason is I've got five different writing projects with different style conventions, and I want the tooling to adapt to the project instead of me remembering which rules apply where.

---

## Stakeholder register

For PR descriptions, design-doc summaries, and updates aimed at reviewers or team leads under time pressure. Lead with the takeaway; let the reader stop after the first sentence if that's all they need.

> Adds a retry policy argument to the worker initializer. Default behavior is unchanged (3 retries with exponential backoff), so existing code is unaffected. Callers who want different behavior can pass a `RetryPolicy` struct — see the new section in `docs/retries.md` for the supported shapes. The motivation is a specific class of job where the default backoff is too aggressive and we're hammering an upstream API we don't own. Tests cover the new argument paths; no changes to the existing retry code paths.

---

## Open-source reader register

For README openings, public-facing project descriptions, and anything aimed at people who find the repo without shared context. Name opinions as opinions; acknowledge the "works for me, your mileage may vary" shape honestly.

> `tally` is a small command-line tool for counting things in text streams — words, regex matches, lines between markers. I wrote it because the combination of `grep | wc -l | awk` is ergonomically rough for anything more complex than basic line counting, and I wanted one tool that could handle the common shapes. Whether it's worth installing depends on how often you find yourself chaining those three commands — if the answer is rarely, `grep | wc` is fine and you don't need this. The tool has opinions: it's fast for the sizes of input I typically work with (low millions of lines), it treats UTF-8 as the default encoding, and it doesn't try to match the flag conventions of any other tool. Those choices work for me; yours may differ.

---

## Civic / public-facing register

For explainers aimed at community audiences — intelligent readers who don't share the author's technical or domain fluency. Define domain terms inline the first time. Never condescend. The goal is accessibility, not simplification.

> Most cities publish their zoning code online, but "publish" is doing a lot of work in that sentence. The code lives in a PDF, the PDF is organized by chapter and section, and a resident with a practical question — can I put a second unit on my lot? what does "setback" (the required distance between a building and the property line) mean for my street? — is expected to read sixty pages to find the answer. The information is public but not accessible, and those are not the same thing. A tool that lets a resident ask the question in plain language and get an answer with citations back into the code doesn't make the code simpler — the code is complicated for reasons — but it shrinks the gap between "technically available" and "actually usable."

---

## Critique / pushback register

For design-doc feedback, architectural disagreement, and any writing that needs to push back on a claim or proposal. Name what's right first, state the concern specifically, propose a forward move.

> The proposal is mostly right — the durability concern is real and checkpointing to Redis is a reasonable answer. Two concerns worth raising before we commit. First, a checkpoint after every step doubles write traffic on a system that's already near its Redis bandwidth ceiling in peak hours; we should measure the cost on a realistic workload before shipping. Second, the recovery story assumes workers return within the job's timeout, which holds for crashes but not for deploys that roll workers slowly. Worth testing both paths. Happy to pair on the measurement piece if useful.
