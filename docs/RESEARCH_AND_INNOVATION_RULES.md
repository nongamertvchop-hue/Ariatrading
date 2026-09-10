# Research & Innovation Rules

These rules define how Ariatrading is developed. They apply alongside the existing research-safety, data-integrity, validation, and paper/demo constraints.

## 1. Build what does not yet exist

Do not limit development to copying existing trading systems or reproducing familiar patterns.
When a real problem is identified, we should be willing to design and implement a new mechanism, architecture, algorithm, visualization, validation method, or research workflow when it can be justified technically.

## 2. Explore like researchers

Treat important development work as research:

- formulate a hypothesis;
- identify assumptions and failure modes;
- implement a measurable experiment;
- test against appropriate data;
- compare against a baseline when one exists;
- record what happened;
- reject ideas that do not survive evidence;
- preserve reproducible results and provenance.

A novel idea is not considered successful merely because it looks impressive. It must survive testing and honest analysis.

## 3. Create new ideas together

Ariatrading is developed collaboratively. The user and the engineering agent should actively propose, challenge, combine, and refine ideas rather than treating the existing design as fixed.

When an opportunity for something genuinely new appears, investigate it instead of automatically choosing the conventional implementation.

## 4. Failure is research data

Failures, unexpected behavior, negative results, and rejected hypotheses are useful evidence.
Do not hide failures or tune experiments until they produce a preferred result. Record the failure, identify the root cause, and use it to improve the next experiment.

## 5. Novelty must not override engineering safety

Innovation never justifies disabling safeguards.
New trading ideas must remain subject to:

- no look-ahead bias or future-data leakage;
- deterministic/reproducible testing where practical;
- explicit validation boundaries;
- failure-closed behavior at safety-critical boundaries;
- separation of strategy, research, simulation, and execution concerns;
- paper/demo testing before any consideration of a live execution boundary.

## 6. Never confuse invention with proof

A new mechanism may be promising without being proven effective.
Use precise language such as **hypothesis**, **experimental**, **candidate**, **validated**, or **not validated** according to the evidence available.
Never present backtest or simulation results as proof of future performance.

## 7. Prefer measurable novelty

When inventing something new, define how it will be evaluated before relying on it. Useful evidence may include robustness across chronological windows, out-of-sample behavior, ablation tests, sensitivity analysis, failure-case analysis, and reproducibility.

## 8. Protect the existing system while experimenting

Experimental work should be isolated when possible. A new research idea must not silently alter the established strategy semantics, corrupt historical comparability, or break the paper/demo safety contract.

## Core principle

> **Create what does not exist. Test it like a researcher. Keep what survives evidence. Learn from what fails. Never sacrifice safety or scientific honesty for novelty.**
