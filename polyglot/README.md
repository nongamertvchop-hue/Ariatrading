# Ariatrading Polyglot Verification Fabric

## Purpose

The Polyglot Verification Fabric (PVF) is an experimental research layer for making many programming-language runtimes cooperate without allowing language diversity to weaken trading safety.

The design treats programming languages as **independent validators, simulators, research workers, and formal-checking workers** around a shared contract. It does not duplicate the core trading strategy in dozens of languages.

That distinction matters: duplicating entry logic across many implementations would create semantic drift and multiply bugs.

## Safety invariants

1. PVF is research/validation infrastructure.
2. A worker cannot create a third strategy direction.
3. Consensus can validate an existing LONG/SHORT/WAIT decision, but cannot invent one.
4. Invalid, missing, timed-out, or malformed workers fail closed.
5. No worker receives a credential or surface for LIVE broker execution.
6. Broker-facing execution remains behind the existing system gate and demo/paper boundary.
7. Historical research keeps chronological and causal boundaries intact.

## Why not compile every language into the browser?

That would be the wrong architecture. Many listed languages are niche, toolchain-dependent, graphical, formal, hardware-description, or accelerator languages. Some are better suited to proof, optimization, simulation, GPU kernels, or embedded execution than to a web trading terminal.

PVF therefore separates **capability** from **runtime availability**. The registry describes the full requested language universe, while the runner executes only installed workers that implement the contract.

## Worker contract

A worker reads one JSON request from stdin and emits exactly one JSON response on stdout.

Request:

```json
{
  "schema_version": "1.0",
  "request_id": "abc-123456",
  "task": "validate_market_snapshot",
  "payload": {}
}
```

Response:

```json
{
  "schema_version": "1.0",
  "request_id": "abc-123456",
  "ok": true,
  "result": {}
}
```

The runner validates version, request identity, response shape, exit status, and timeout. Any violation becomes a failed worker result.

## Intended division of labor

- **C/C++/Rust/Zig/D/Ada**: deterministic low-level validators, fast simulation kernels, memory-sensitive workloads.
- **Java/C#/Kotlin/Scala/F#/VB.NET/Groovy**: service-oriented research workers and JVM/.NET ecosystem integration.
- **Python/R/MATLAB/Julia/Octave/Scilab/Mathematica/Maple/Maxima/Stata/SAS/SPSS**: statistics, research, optimization, model evaluation, and scientific analysis.
- **JavaScript/TypeScript/PHP/Ruby/Lua/Dart**: web-adjacent tooling, orchestration, and lightweight workers.
- **SQL**: dataset integrity, aggregation, lineage checks, and research queries rather than strategy execution.
- **Bash/PowerShell**: build/test/deployment orchestration only.
- **CUDA/OpenCL/OpenMP/MPI/Chapel/X10/HPF/ZPL**: parallel numerical research where a measured benchmark proves the complexity is worthwhile.
- **Verilog/VHDL/SystemVerilog/GLSL/HLSL/WGSL**: specialized hardware/GPU experimentation, never an unreviewed broker path.
- **Coq/Agda/Idris/Lean/TLA+/Alloy/Promela/MiniZinc**: formal specification, invariant checking, model checking, and constraint validation.
- **Solidity/Vyper/Move/Cairo**: isolated smart-contract/blockchain research only; never coupled to broker credentials by default.
- **Arduino/Wiring/Processing/Scratch**: education, visualization, prototyping, or hardware experiments.

This mapping is a research role proposal, not a claim that every runtime is already implemented in the repository.

## Experimental research direction

PVF enables a new class of experiments: **cross-implementation disagreement as a first-class research signal**. When independent implementations receive the same immutable snapshot and contract, disagreement is recorded as evidence rather than silently averaged away.

A future research controller can compare:

`Python result != Rust result != C++ result != formal-check result`

and classify the event as a reproducibility failure, numeric-boundary issue, specification ambiguity, or implementation bug before the result is allowed into downstream evidence.

This is intentionally an experimental architecture. Novelty is treated as a hypothesis until benchmarked, reproduced, and falsified where possible.
