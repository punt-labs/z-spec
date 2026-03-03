# Research: Formal Specifications and LLM-Based Coding Assistants
**Date:** 2026-03-03
**Request:** Search for industry references, academic papers, and blog posts about using formal specifications (Z notation, TLA+, Alloy, B-Method, or similar) together with AI coding assistants or LLMs, covering: (1) formal specs as contracts LLMs verify code against, (2) LLMs generating or checking formal specifications, (3) combining formal methods with AI for bug finding or code generation. Focus 2023-2026.
**Claims investigated:** 3

---

## Evidence Found

---

**Claim**: Formal specifications can make LLM-based coding assistants more effective at finding bugs.
**Verdict**: PARTIALLY SUPPORTED
**Sources**:

- **Councilman et al. 2025 (Astrogator / arXiv:2507.13290)**: Implemented a formal query language as a contract layer over Ansible. An LLM generates code; a symbolic interpreter verifies correctness against the spec. The verifier confirmed correct code in 83% of cases and identified incorrect code in 92% of cases. This is the strongest direct evidence: a formal spec acting as a correctness oracle for LLM-generated code.

- **Richter & Wehrheim 2025 (NL2Contract / arXiv:2510.12702)**: LLMs can infer both preconditions and postconditions from natural-language cues in code signatures and documentation. Verifiers supplied with these LLM-inferred contracts produced fewer false alarms than verifiers supplied with postconditions alone, and the inferred preconditions enabled detection of genuine bugs in real-world code.

- **PropertyGPT 2025 (NDSS)**: LLM-generated properties for smart contract verification achieved 80% recall against human-written ground-truth properties. The system found 26 known vulnerabilities and uncovered 12 previously unknown ones, yielding $8,256 in bug bounty rewards.

- **Beg, O'Donoghue & Monahan 2026 (ACSL/Frama-C / arXiv:2602.13851)**: Compared tool-generated vs LLM-generated ACSL annotations for 506 C programs verified by Frama-C WP. Tool-generated (RTE plugin) annotations achieved near-100% proof success. LLM-generated annotations (DeepSeek, GPT-5.2, OLMo3) showed lower and more variable success rates. The key finding is that LLM expressiveness causes increased SMT solver sensitivity and timeouts.

- **Jin & Chen 2025 (arXiv:2508.12358, ASE'25)**: LLMs exhibit a systematic "over-correction bias" when asked to verify code against natural-language specifications. GPT-4o accuracy on HumanEval dropped from 52.4% with simple prompts to 11.0% with multi-step prompts. LLMs misclassify correct code as failing far more often under complex prompt chains.

- **Bharadwaj et al. 2026 (Constitutional SDD / arXiv:2602.02584)**: Embeds non-negotiable security constraints derived from CWE/MITRE Top 25 into a machine-readable "Constitution" specification layer. When LLM-generated code is constrained to meet this formal spec, the approach achieved a 73% reduction in security defects compared to unconstrained AI generation. 10 critical CWE vulnerability classes were addressed. Developer velocity was maintained. The mechanism is spec-as-precondition (spec gates generation), which is a different but complementary approach to spec-as-oracle.

- **Abebe 2026 (Specification-Driven Development / arXiv:2602.00180)**: Practitioner-oriented AIWare 2026 paper establishing a three-level taxonomy of specification rigor (spec-first, spec-anchored, spec-as-source). Examines tools from BDD frameworks to GitHub Spec Kit. Does not report controlled bug-finding results; primarily a framework paper positioning formal specs as the primary development artifact in AI-assisted workflows.

**Contradictory evidence**:
- The ACSL/Frama-C study (Beg 2026) shows LLM-generated specs are less reliable than tool-generated ones for machine verification -- they introduce SMT solver instability. Formal specs written by LLMs, as opposed to specs used to check LLM output, are not yet trustworthy without a verification feedback loop.
- The Jin & Chen ASE'25 study shows LLMs used as the verifier (checking code against NL specs) fail systematically. The benefit is only realised when a separate formal checker (not the LLM itself) does the verification.
- SysMoBench (Cheng et al. 2025/2026, arXiv:2509.23130) benchmarks LLMs on constructing TLA+ models of real distributed systems and finds significant performance gaps for complex artifacts, indicating LLM-generated formal models are not yet reliable without human oversight.
- VeriSoftBench (Bursuc et al. 2026, arXiv:2602.18307): 500-proof Lean 4 benchmark drawn from real open-source formal-methods repositories. Mathlib-tuned systems transfer poorly; dependency complexity strongly correlates with failure. Establishes that real-world verification contexts are substantially harder than mathematical proof benchmarks.

**Recommendation**: The claim is defensible with an important caveat: the mechanism that works is using a formal spec as a machine-checkable oracle that LLM output is verified against -- not asking the LLM itself to do the verification. Revise to: "Formal specifications used as machine-checkable contracts can increase the reliability of LLM-generated code; the formal checker, not the LLM, must perform the verification step."

---

**Claim**: LLMs can generate or check formal specifications.
**Verdict**: PARTIALLY SUPPORTED
**Sources**:

- **Faria et al. 2026 (arXiv:2601.12845, Dafny)**: Using Claude Opus 4.5 and GPT-5.2 with a verifier feedback loop, LLMs generated correct formal annotations (preconditions, postconditions, loop invariants) for 98.2% of 110 Dafny programs within at most 8 repair iterations. Without the iterative repair loop this success rate is substantially lower -- the loop is load-bearing.

- **Cunha & Macedo 2025 (arXiv:2510.23350, Alloy)**: GPT-5 generated syntactically correct positive and negative test cases for Alloy formal specifications effectively, detecting many wrong specifications written by humans. Frames LLM as a spec-validation assistant rather than a spec generator.

- **Alhanahnah et al. 2024 (arXiv:2404.11050, Alloy repair)**: Dual-agent LLM setup with auto-prompting outperforms prior state-of-the-art automated program repair techniques for buggy Alloy specifications. First empirical evaluation of LLMs on declarative formal spec repair.

- **Bursuc et al. 2025 (VeriCoding benchmark, arXiv:2509.22908)**: LLMs generating Dafny from formal specs achieved 82% success; Verus/Rust 44%; Lean 27%. Dafny success improved from 68% to 96% over approximately one year of LLM progress, showing rapid improvement. Natural language descriptions alongside specs did not substantially improve performance.

- **Zhou & Tripakis 2025 (arXiv:2512.09758, TLA+)**: LLM-guided hierarchical decomposition of TLA+ proof obligations into simpler sub-claims, then passed to symbolic TLAPS provers, consistently outperforms baseline approaches on a benchmark of 119 theorems from distributed protocol proofs.

- **Patil, Ung & Nyberg 2024 (arXiv:2411.13269, automotive ACSL)**: spec2code framework: LLM generates C code from ACSL formal specifications with an iterative feedback loop. Evaluated on three Scania industrial case studies; formally correct code can be generated even without iterative backprompting in simple cases.

- **Kuramoto et al. 2026 (AutoReal / arXiv:2602.08384, seL4 Isabelle/HOL)**: Fine-tuned 7B-parameter open-source LLM (AutoReal-Prover) with chain-of-thought proof training and context augmentation. Achieved 51.67% proof success on 660 seL4 theorems (up from prior best of 27.06%) and 53.88% on 451 theorems from three security-related AFP projects. First demonstration that a compact locally-deployable model can approach industrial-scale Isabelle/HOL verification.

- **VeriSoftBench 2026 (arXiv:2602.18307, Lean 4)**: 500 proof obligations from real open-source formal-methods repositories. Mathlib-tuned systems transfer poorly to this setting; dependency complexity strongly correlates with failure; curated context helps but substantial gaps remain. Establishes a harder, more realistic evaluation regime for LLM-based proof generation.

**Contradictory evidence**:
- Beg et al. 2026 (ACSL): LLM-generated annotations are less reliable and less stable than tool-generated ones. Expressiveness comes at the cost of solver instability.
- VeriCoding benchmark (Bursuc 2025): Success rates on Lean (27%) and Verus/Rust (44%) remain low, meaning LLM-to-formal-spec generation is language-dependent and far from solved.
- SysMoBench (Cheng et al. 2026): LLMs struggle with complex real-world distributed system artifacts in TLA+. Small, self-contained systems work; large real systems do not.

**Recommendation**: Use with nuance. LLMs can generate and repair formal specifications in restricted settings with verifier feedback, but success is highly sensitive to (a) the complexity of the target system, (b) whether a machine checker provides corrective feedback, and (c) which formal language is used. State the caveat explicitly.

---

**Claim**: Combining formal methods with AI tools for bug finding or code generation (general claim).
**Verdict**: SUPPORTED (as an active research direction with demonstrated results; not yet a mature production practice)
**Sources**:

- **Kleppmann 2025 (blog)**: Argues that LLM-generated proof scripts + formal proof checkers create a virtuous cycle: the checker rejects invalid proofs and forces LLM retry, preventing hallucination propagation. Cites seL4 verification cost (8,700 lines C, 20 person-years, 200,000 lines Isabelle) as evidence that historical cost barrier is collapsing. Mentions Harmonic's Aristotle, Logical Intelligence, DeepSeek-Prover-V2 as commercial entrants. This is a secondary/opinion source, but well-evidenced.

- **Ferrari & Spoletini 2025 (Information and Software Technology, DOI:10.1016/j.infsof.2025.107697)**: Peer-reviewed journal roadmap paper. Proposes two symmetric roadmaps: (1) use formal methods to provide correctness/fairness/trustworthiness guarantees for LLM-generated RE artifacts; (2) use LLMs to make formal methods more accessible to practitioners. Covers Z specification and formal verification explicitly. Does not report benchmark results -- this is a position/roadmap paper.

- **Beg, O'Donoghue & Monahan 2025 (arXiv:2507.14330)**: VERIFAI project survey identifies the conversion of informal NL requirements to formal specs as the critical bottleneck for safety-critical systems. LLMs are the leading candidate to bridge this gap. Identifies ambiguity, missing domain knowledge, contextual gaps, and prompt instability as open challenges.

- **Woodcock et al. 2009 (ACM Surveys)**: Historical baseline -- 92% of formal methods practitioners reported quality increases, 0% reported decreases, but little cost-benefit data. Establishes that formal methods do improve quality; the 2024-2026 literature addresses whether LLMs can make formal methods more accessible.

**Contradictory evidence**:
- Xu et al. 2024 (arXiv:2401.11817, "Hallucination is Inevitable"): Proves theoretically via diagonalization that LLMs cannot learn all computable functions, making hallucination in formal/logical domains structurally inevitable without external symbolic reasoning. This does not refute the hybrid approach but sets a ceiling: LLMs alone cannot be the verification engine.

**Recommendation**: The combination is a credible and actively productive research direction. The productive architecture is LLM (generation/repair) plus formal checker (verification) in a feedback loop -- not LLMs as sole verifiers. This is supported by multiple independent research groups in 2024-2026.

---

## Overall Verdict on the Central Claim

"Formal specifications can make LLM-based coding assistants more effective at finding bugs."

**PARTIALLY SUPPORTED.** The evidence from 2024-2026 supports a more precise version: *when a formal specification is used as a machine-checkable contract and the verification is performed by a formal tool (not the LLM), LLM-generated code can be reliably evaluated against that spec, improving bug detection rates.* The weakest link is spec generation -- LLM-generated specs are less stable than tool-generated specs for complex systems. The strongest supporting evidence is Astrogator (83%/92% correct/incorrect detection), PropertyGPT (80% recall, 12 new bugs found), Constitutional SDD (73% security defect reduction), and VeriCoding (82% Dafny success, rapid year-on-year improvement). The strongest contradicting evidence is the "over-correction bias" study (Jin & Chen ASE'25) and Beg et al.'s finding that LLM annotation expressiveness destabilizes SMT solvers.

---

## Bibliography Entries

```bibtex
@misc{councilman2025astrogator,
  author       = {Councilman, Aaron and Fu, David Jiahao and Gupta, Aryan and
                  Wang, Chengxiao and Grove, David and Wang, Yu-Xiong and Adve, Vikram},
  title        = {Towards Formal Verification of {LLM}-Generated Code from
                  Natural Language Prompts},
  year         = {2025},
  url          = {https://arxiv.org/abs/2507.13290},
  note         = {Proposes a formal query language as a contract layer for
                  LLM-generated Ansible code; verifier achieves 83\% confirmation
                  of correct code and 92\% identification of incorrect code.},
}

@misc{richter2025nl2contract,
  author       = {Richter, Cedric and Wehrheim, Heike},
  title        = {Beyond Postconditions: Can Large Language Models infer Formal
                  Contracts for Automatic Software Verification?},
  year         = {2025},
  url          = {https://arxiv.org/abs/2510.12702},
  note         = {NL2Contract: LLMs infer full functional contracts (pre- and
                  postconditions); verifiers using these produce fewer false alarms
                  and detect genuine bugs in real-world code.},
}

@inproceedings{liu2025propertygpt,
  author       = {Liu, Ye and Xue, Yue and Wu, Daoyuan and Sun, Yuqiang and
                  Li, Yi and Shi, Miaolei and Liu, Yang},
  title        = {{PropertyGPT}: {LLM}-driven Formal Verification of Smart
                  Contracts through Retrieval-Augmented Property Generation},
  booktitle    = {Proceedings of the Network and Distributed System Security
                  Symposium (NDSS)},
  year         = {2025},
  url          = {https://www.ndss-symposium.org/ndss-paper/propertygpt-llm-driven-formal-verification-of-smart-contracts-through-retrieval-augmented-property-generation/},
  note         = {Achieves 80\% recall against human-written ground-truth properties;
                  finds 26 known and 12 previously unknown vulnerabilities.},
}

@misc{beg2026acsl,
  author       = {Beg, Arshad and O'Donoghue, Diarmuid and Monahan, Rosemary},
  title        = {Evaluating {LLM}-Generated {ACSL} Annotations for Formal
                  Verification},
  year         = {2026},
  url          = {https://arxiv.org/abs/2602.13851},
  note         = {Comparative study of 5 annotation strategies on 506 C programs.
                  Tool-generated (RTE plugin) achieves near 100\% proof success;
                  LLM-generated annotations show lower, more variable rates and
                  increased SMT solver instability.},
}

@inproceedings{jin2025overcorrection,
  author       = {Jin, Haolin and Chen, Huaming},
  title        = {Uncovering Systematic Failures of {LLMs} in Verifying Code
                  Against Natural Language Specifications},
  booktitle    = {ASE 2025: 40th IEEE/ACM International Conference on Automated
                  Software Engineering},
  year         = {2025},
  url          = {https://arxiv.org/abs/2508.12358},
  note         = {Identifies over-correction bias: GPT-4o accuracy on HumanEval
                  falls from 52.4\% to 11.0\% as prompt complexity increases.
                  Key contradictory evidence for LLMs-as-verifiers.},
}

@misc{faria2026dafny,
  author       = {Faria, Jo\~{a}o Pascoal and Trigo, Emanuel and Honorato, Vinicius
                  and Abreu, Rui},
  title        = {Automatic Generation of Formal Specification and Verification
                  Annotations Using {LLMs} and Test Oracles},
  year         = {2026},
  url          = {https://arxiv.org/abs/2601.12845},
  note         = {Combined Claude Opus 4.5 and GPT-5.2 generate correct Dafny
                  annotations for 98.2\% of 110 programs within 8 repair iterations
                  using verifier feedback.},
}

@misc{cunha2025alloy,
  author       = {Cunha, Alcino and Macedo, Nuno},
  title        = {Validating Formal Specifications with {LLM}-generated Test Cases},
  year         = {2025},
  url          = {https://arxiv.org/abs/2510.23350},
  note         = {GPT-5 generates syntactically correct positive/negative Alloy
                  test cases from NL requirements; detects many wrong specifications
                  written by humans.},
}

@misc{alhanahnah2024alloyrepair,
  author       = {Alhanahnah, Mohannad and Hasan, Md Rashedul and Xu, Lisong and
                  Bagheri, Hamid},
  title        = {An Empirical Evaluation of Pre-trained Large Language Models
                  for Repairing Declarative Formal Specifications},
  year         = {2024},
  url          = {https://arxiv.org/abs/2404.11050},
  note         = {First empirical study of LLMs repairing buggy Alloy specs.
                  Dual-agent with auto-prompting outperforms state-of-the-art
                  Alloy APR techniques.},
}

@misc{bursuc2025vericoding,
  author       = {Bursuc, Sergiu and Ehrenborg, Theodore and Lin, Shaowei and
                  Astefanoaei, Lacramioara and Chiosa, Ionel Emilian and Kukovec, Jure
                  and Singh, Alok and Butterley, Oliver and Bizid, Adem and
                  Dougherty, Quinn and Zhao, Miranda and Tan, Max and Tegmark, Max},
  title        = {A benchmark for vericoding: formally verified program synthesis},
  year         = {2025},
  url          = {https://arxiv.org/abs/2509.22908},
  note         = {12,504-problem benchmark (Dafny, Verus/Rust, Lean). LLM success:
                  82\% Dafny, 44\% Verus/Rust, 27\% Lean. Dafny improved 68\%
                  to 96\% in one year.},
}

@misc{zhou2025tlaproof,
  author       = {Zhou, Yuhao and Tripakis, Stavros},
  title        = {Towards Language Model Guided {TLA+} Proof Automation},
  year         = {2025},
  url          = {https://arxiv.org/abs/2512.09758},
  note         = {LLMs guide hierarchical decomposition of TLA+ proof obligations
                  into sub-claims; symbolic TLAPS provers handle verification.
                  Outperforms baselines on 119-theorem benchmark.},
}

@misc{cheng2025sysmobench,
  author       = {Cheng, Qian and Tang, Ruize and Ma, Emilie and Hackett, Finn and
                  He, Peiyang and Su, Yiming and Beschastnikh, Ivan and Huang, Yu and
                  Ma, Xiaoxing and Xu, Tianyin},
  title        = {{SysMoBench}: Evaluating {AI} on Formally Modeling Complex
                  Real-World Systems},
  year         = {2025},
  url          = {https://arxiv.org/abs/2509.23130},
  note         = {Benchmarks LLMs on constructing TLA+ models of real distributed
                  systems (Raft/Etcd, ZooKeeper, Asterinas OS). LLMs handle small
                  artifacts; significant gaps remain for complex real-world systems.},
}

@misc{patil2024spec2code,
  author       = {Patil, Minal Suresh and Ung, Gustav and Nyberg, Mattias},
  title        = {Towards Specification-Driven {LLM}-Based Generation of Embedded
                  Automotive Software},
  year         = {2024},
  url          = {https://arxiv.org/abs/2411.13269},
  note         = {spec2code framework: LLM generates C code from ACSL formal specs
                  with iterative critic feedback. Evaluated on three Scania industrial
                  case studies.},
}

@misc{beg2025verifai,
  author       = {Beg, Arshad and O'Donoghue, Diarmuid and Monahan, Rosemary},
  title        = {Leveraging {LLMs} for Formal Software Requirements: Challenges
                  and Prospects},
  year         = {2025},
  url          = {https://arxiv.org/abs/2507.14330},
  note         = {VERIFAI project survey: NL-to-formal-spec conversion is the
                  critical bottleneck; identifies ambiguity, missing domain knowledge,
                  and prompt instability as open challenges.},
}

@online{kleppmann2025fvmainstream,
  author       = {Kleppmann, Martin},
  title        = {Prediction: {AI} will make formal verification go mainstream},
  year         = {2025},
  url          = {https://martin.kleppmann.com/2025/12/08/ai-formal-verification.html},
  urldate      = {2026-03-03},
  note         = {Argues LLM proof-script generation + formal checkers will make
                  verification economically viable. Secondary/opinion but cites
                  concrete examples (seL4, CompCert) and commercial entrants.},
}

@misc{xu2024hallucination,
  author       = {Xu, Ziwei and Jain, Sanjay and Kankanhalli, Mohan},
  title        = {Hallucination is Inevitable: An Innate Limitation of Large
                  Language Models},
  year         = {2024},
  url          = {https://arxiv.org/abs/2401.11817},
  note         = {Proves via diagonalization that LLMs cannot eliminate hallucination
                  for all computable functions; sets a theoretical ceiling for
                  LLMs-as-verifiers without external symbolic reasoning.},
}

@misc{bharadwaj2026constitutionalsdd,
  author       = {Bharadwaj, Suhas and {others}},
  title        = {Constitutional Spec-Driven Development: Enforcing Security by
                  Construction in {AI}-Assisted Code Generation},
  year         = {2026},
  url          = {https://arxiv.org/abs/2602.02584},
  note         = {Embeds CWE/MITRE-derived security constraints in a machine-readable
                  Constitution spec layer. 73\% reduction in security defects vs
                  unconstrained AI generation; developer velocity maintained.},
}

@misc{abebe2026sdd,
  author       = {Abebe, Solomon Lemma},
  title        = {Specification-Driven Development: Rethinking How We Build Software
                  in the Age of {AI}},
  year         = {2026},
  url          = {https://arxiv.org/abs/2602.00180},
  note         = {AIWare 2026 practitioner paper. Three-level taxonomy of spec rigor
                  (spec-first, spec-anchored, spec-as-source). Positions formal specs
                  as primary artifact in AI-assisted development. No controlled
                  empirical results.},
}

@misc{kuramoto2026autoreal,
  author       = {Kuramoto, Hideo and {others}},
  title        = {Towards Real-World Industrial-Scale Verification: {LLM}-Driven
                  Theorem Proving on {seL4}},
  year         = {2026},
  url          = {https://arxiv.org/abs/2602.08384},
  note         = {Fine-tuned 7B-parameter AutoReal-Prover with chain-of-thought
                  training achieves 51.67\% on 660 seL4 Isabelle/HOL theorems
                  (prior best 27.06\%) and 53.88\% on 451 AFP security theorems.},
}

@misc{bursuc2026verisoftbench,
  author       = {Bursuc, Sergiu and {others}},
  title        = {{VeriSoftBench}: Repository-Scale Formal Verification Benchmarks
                  for {Lean}},
  year         = {2026},
  url          = {https://arxiv.org/abs/2602.18307},
  note         = {500 Lean 4 proof obligations from real open-source formal-methods
                  repos. Mathlib-tuned systems transfer poorly; dependency complexity
                  correlates with failure; substantially harder than mathematical
                  proof benchmarks.},
}

@article{ferrari2025roadmap,
  author       = {Ferrari, Alessio and Spoletini, Paola},
  title        = {Formal requirements engineering and large language models:
                  A two-way roadmap},
  journal      = {Information and Software Technology},
  volume       = {181},
  pages        = {107697},
  year         = {2025},
  doi          = {10.1016/j.infsof.2025.107697},
  note         = {Peer-reviewed journal roadmap. Two symmetric paths: formal methods
                  to guarantee LLM RE artifact correctness; LLMs to make formal
                  methods (including Z specification) more accessible.},
}
```

---

## Research Gaps

**Claim / Area**: Z notation and B-Method specifically with LLMs.
**What's missing**: No 2023-2026 paper was found that uses Z notation (ISO standard) or the B-Method / Event-B directly in combination with an LLM coding assistant. All found work uses Dafny, TLA+, Alloy, ACSL/Frama-C, Lean, or Isabelle/HOL. Ferrari & Spoletini 2025 mentions Z in scope but does not provide experimental results for Z specifically. This is a genuine gap: the Z/B ecosystem (ProB, fuzz) is not represented in the LLM+formal-methods empirical literature.
**Suggested action**: The gap is evidence that Z and B have not yet been studied in this context. Do not claim otherwise. If needed for a research proposal, position this as a novel research opportunity.

**Claim / Area**: Production deployment data for formal-spec-guided LLM code generation.
**What's missing**: All found results are research prototypes or benchmarks. The Constitutional SDD paper (arXiv:2602.02584) comes closest to a production-style evaluation (73% security defect reduction) but is a banking case study, not a longitudinal production deployment. The Scania case study (spec2code) is an industrial evaluation but preliminary.
**Suggested action**: Accept as assumption in any PR/FAQ; flag the gap explicitly.

**Claim / Area**: Comparative effectiveness vs no-spec baseline at scale.
**What's missing**: Most studies report internal metrics (e.g., 83% verifier acceptance) without a head-to-head comparison against an LLM coding assistant with no formal spec at all, on the same task. Jin & Chen (2025) is the exception but studies a different failure mode. Constitutional SDD does provide a controlled comparison (73% reduction vs unconstrained baseline).
**Suggested action**: Use Constitutional SDD as the primary comparative evidence; note it is limited to security properties.
