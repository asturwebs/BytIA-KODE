#### _[Do not be seduced by praise, nor afraid of slander; follow the Way steadfastly and conduct oneself uprightly.](https://x.com/teortaxesTex/status/2047522061459898427)_

<br>
<br>

DeepSeek dropped a landmark [technical report](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro/blob/main/DeepSeek_V4.pdf) for its V4 series packed with infra and efficiency hacks. I've gone through the report and tried to break it all down here so that anyone & everyone can follow along and understand it. For a shorter version please checkout elie's thread [here](https://x.com/eliebakouch/status/2047519300399837677).

_Note that this is a "preview" release. More on why that matters later._

---

The emergence of reasoning models has established a new paradigm of test-time scaling, driving substantial performance gains for Large Language Models. However, this scaling paradigm is fundamentally constrained by the quadratic computational complexity of the vanilla attention mechanism, which creates a prohibitive bottleneck for ultra-long contexts and reasoning processes. Concurrently, the emergence of long-horizon scenarios and tasks, from complex agentic workflows to massive cross-document analysis, has made efficient support for ultra-long contexts critical for future progress. While recent open-source efforts have advanced general capabilities, this core architectural inefficiency in handling ultra-long sequences remains a key impediment, limiting further gains from test-time scaling and hindering further exploration into long-horizon scenarios and tasks.


![Figure 1](images/v4/figure1.png)

The right part demonstrates the estimated single-token inference FLOPs and accumulated KV cache size of DeepSeek-V3.2 and DeepSeek-V4 series. In the scenario of 1M-token context, even DeepSeek-V4-Pro, which has a larger number of activated parameters, attains only 27% of the single-token FLOPs (measured in equivalent FP8 FLOPs) and 10% of the KV cache size relative to DeepSeek-V3.2. Furthermore, DeepSeek-V4-Flash pushes efficiency even further. In the 1M-token context setting, it achieves only 10% of the single-token FLOPs and 7% of the KV cache size compared with DeepSeek-V3.2.

The left part shows benchmark performance of DeepSeek-V4-Pro-Max and its counterparts. DeepSeek-V4-Pro-Max, the maximum reasoning effort mode of DeepSeek-V4-Pro, redefines the state-of-the-art for open models, outperforming its predecessors in core tasks. On coding competitions, their performance is comparable to GPT-5.4, making this the first time an open model has matched a closed model on this task.


## Architectural Change.

Compared with the DeepSeek-V3 architecture, DeepSeek-V4 series retain the DeepSeekMoE framework and Multi-Token Prediction (MTP) strategy, while introducing several key innovations in architecture and optimization. For the MoE components, DeepSeek-V4 series adopt the DeepSeekMoE paradigm for Feed-Forward Networks, which sets fine-grained routed experts and shared experts. Compared with DeepSeek-V3, they replace the dense FFN layers in the initial several Transformer blocks with MoE layers that employ Hash routing. The Hash routing strategy determines the target experts of each token according to a predefined hash function with regard to the input token ID. For load balancing, they also employ the auxiliary-loss-free strategy, augmented by a slight sequence-wise balance loss that prevents extreme imbalance within individual sequences. The MTP configuration remains identical to that of DeepSeek-V3.

**MLA is gone.** To enhance long-context efficiency, they design a hybrid attention mechanism combining Compressed Sparse Attention (CSA) and Heavily Compressed Attention (HCA). CSA compresses the KV caches along the sequence dimension and then performs DeepSeek Sparse Attention (DSA), whereas HCA applies more aggressive compression to the KV caches but keeps dense attention.

They also incorporate [Manifold-Constrained Hyper-Connections](https://k-a.in/mHC.html) (mHC) to strengthen conventional residual connections. The standard HC expands the width of the residual stream by a factor of $n_{\text{hc}}$ (set to 4 in DeepSeek-V4). HC introduces three linear mappings. An input mapping $A_l \in \mathbb{R}^{1 \times n_{\text{hc}}}$, a residual transformation $B_l \in \mathbb{R}^{n_{\text{hc}} \times n_{\text{hc}}}$, and an output mapping $C_l \in \mathbb{R}^{n_{\text{hc}} \times 1}$. The update of the residual state is

$$X_{l+1} = B_l X_l + C_l \mathcal{F}_l(A_l X_l)$$

The core innovation of mHC is to constrain the residual mapping matrix $B_l$ to the manifold of doubly stochastic matrices (the Birkhoff polytope)

$$B_l \in \mathcal{M} \coloneqq \{M \in \mathbb{R}^{n \times n} \mid M\mathbf{1}_n = \mathbf{1}_n,\ \mathbf{1}_n^T M = \mathbf{1}_n^T,\ M \geq 0\}$$

This constraint ensures that the spectral norm of the mapping matrix $\|B_l\|_2$ is bounded by 1, so the residual transformation is non-expansive, which increases the numerical stability during both the forward pass and backpropagation. The set $\mathcal{M}$ is closed under multiplication, which guarantees stability in the scenarios of deep stacks of mHC. The input transformation $A_l$ and output transformation $C_l$ are also constrained to be non-negative and bounded via a Sigmoid function to avoid the risk of signal cancellation. The parameters of three linear mappings are dynamically generated, decomposed into a dynamic (input-dependent) component and a static (input-independent) component.

Additionally, they introduce the Muon optimizer to the training of DeepSeek-V4 series, leading to faster convergence and improved training stability.

---

**CSA**, the centerpiece of the hybrid attention architecture.

![Figure 3, CSA Architecture](images/v4/figure3_csa.png)

The core architecture of CSA first compresses the KV cache of each $m$ tokens into one entry, and then applies DeepSeek Sparse Attention for further acceleration. Additionally, a small set of sliding window KV entries is combined with the selected compressed KV entries to enhance local fine-grained dependencies.

**Compressed Key-Value Entries.** Let $H \in \mathbb{R}^{n \times d}$ be a sequence of input hidden states, where $n$ is the sequence length and $d$ is the hidden size. CSA first computes two series of KV entries $C_a, C_b \in \mathbb{R}^{n \times c}$ and their corresponding compression weights $Z_a, Z_b \in \mathbb{R}^{n \times c}$

$$C_a = H \cdot W_a^{KV},\quad C_b = H \cdot W_b^{KV}$$
$$Z_a = H \cdot W_a^Z,\quad Z_b = H \cdot W_b^Z$$

Each $m$ KV entries in $C_a$ and $C_b$ are compressed into one entry according to their compression weights and learnable positional biases $B_a, B_b \in \mathbb{R}^{m \times c}$

$$[S^a_{mi:m(i+1)-1};\ S^b_{m(i-1):mi-1}] = \text{Softmax}_{\text{row}}([Z^a_{mi:m(i+1)-1} + B_a;\ Z^b_{m(i-1):mi-1} + B_b])$$

$$C_i^{\text{Comp}} = \sum_{j=mi}^{m(i+1)-1} S_j^a \odot C_j^a + \sum_{j=m(i-1)}^{mi-1} S_j^b \odot C_j^b$$

![Equations 11-12, CSA Compression](images/v4/csa_compression.png)

Each $C_i^{\text{Comp}}$ is derived from $2m$ KV entries, but the indexes of $C_b$ used for $C_i^{\text{Comp}}$ and the indexes of $C_a$ used for $C_{i-1}^{\text{Comp}}$ are overlapped. Therefore, CSA in fact compresses the sequence length to $\frac{1}{m}$ times.

**Lightning Indexer for Sparse Selection.** After obtaining the compressed KV entries, CSA applies the DSA strategy to select top-k compressed KV entries for core attention. CSA performs the same compression operation used for $C^{\text{Comp}}$ to get compressed indexer keys. Then, for a query token $t$, indexer queries are produced in a low-rank manner. The index score between the query token $t$ and a preceding compressed block $s$ is

$$I_{t,s} = \sum_{h=1}^{n_h^I} w_{t,h}^I \cdot \text{ReLU}\left(q_{t,h}^I \cdot K_s^{I\text{Comp}}\right)$$

Given the index scores, a top-k selector selectively retains a subset of compressed KV entries for subsequent core attention. The indexer operates on the compressed entries, and the attention computation within the lightning indexer is performed in FP4 precision, which accelerates the attention operation under extremely long contexts.

A supplementary attention branch is introduced in a sliding window manner ($n_{\text{win}} = 128$ uncompressed KV entries), for better modeling of local dependencies. In order to strictly preserve causality in CSA, each query attends to only preceding compressed KV blocks. Consequently, a query cannot access information from other tokens within its own compressed block. Meanwhile, recent tokens usually possess greater relevance to the query token in language modeling. For these reasons, the sliding window provides direct access to the most recent tokens.

After the selected compressed entries and sliding window entries are concatenated, they get passed to Shared Key-Value MQA.

---

**HCA**, the second attention mechanism.

![Figure 4, HCA Architecture](images/v4/figure4_hca.png)

The core architecture of HCA compresses the KV cache in a heavier manner, but does not employ sparse attention. By and large, the compression strategy of HCA is similar to that of CSA, but employs a larger compression rate $m'$ ($\gg m$) and does not perform overlapped compression. Where CSA compresses every $m = 4$ tokens into 1, HCA compresses every $m' = 128$ tokens into 1. Through this compression operation, HCA compresses the sequence length to $\frac{1}{m'}$ times. After compression there are so few entries that sparse selection is unnecessary. HCA keeps dense attention. HCA also employs the shared KV MQA and grouped output projection strategies as CSA does.

CSA and HCA are used in an interleaved manner across layers. For DeepSeek-V4-Flash, the first two layers use pure sliding window attention, and for the subsequent layers, CSA and HCA are interleaved. For DeepSeek-V4-Pro, the first two layers use HCA, and for the subsequent layers, CSA and HCA are interleaved. This hybrid architecture of CSA and HCA remarkably improves the long-context efficiency of DeepSeek-V4 series, making one-million-token context feasible in practice.

---

Both CSA and HCA employ Shared Key-Value Multi-Query Attention (MQA).

![Shared Key-Value MQA](images/v4/shared_kv_mqa.png)

CSA performs core attention in a Multi-Query Attention (MQA) manner, where each compressed KV entry serves as both attention key and value. Queries are produced from a compressed latent vector shared with that used for the indexer queries

$$o_{t,i} = \text{CoreAttn}\left(\text{query}=q_{t,i},\ \text{key}=C_t^{\text{SprsComp}},\ \text{value}=C_t^{\text{SprsComp}}\right)$$

**Grouped Output Projection.** In the configuration of DeepSeek-V4, $cn_h$ is quite large. Therefore, directly projecting the outputs of the core attention operation to a $d$-dimensional hidden state will impose a substantial computational burden. To mitigate this cost, a grouped output projection strategy is designed. The $n_h$ outputs are split into $g$ groups, and for each group, the output is projected to a $d_g$-dimensional intermediate output, where $d_g < c\frac{n_h}{g}$. Finally, the intermediate outputs are projected to the final attention output.

**Partial Rotary Positional Embedding.** For both CSA and HCA, RoPE is partially employed on the attention queries, KV entries, and the core attention outputs. For each query vector and KV entry vector, RoPE is applied to its last 64 dimensions. Since the KV entries serve as both attention keys and values, the naive core attention outputs will carry absolute position embeddings. As a countermeasure, RoPE with position $-i$ is applied on the last 64 dimensions of each output, so the output of the core attention will carry relative position embeddings.

---

**QK Normalization.** For both CSA and HCA, an additional RMSNorm operation is performed on each head of the queries and the only head of the compressed KV entries, just before the core attention operation. This normalization avoids exploding attention logits and may improve training stability.

![QK Normalization](images/v4/qk_norm.png)

The attention architecture of DeepSeek-V4 series allows direct application of RMSNorm on the attention queries and KV entries, which effectively prevents attention logits from exploding. Consequently, the QK-Clip technique is not employed in the Muon optimizer.

---

**Attention Sink.** In the core attention of CSA and HCA, the trick of attention sink is employed. A series of learnable sink logits $\{z'_1, z'_2, \ldots, z'_{n_h}\}$ are set. For the $h$-th attention head, $\exp(z'_h)$ is added to the denominator of the attention score

$$s_{h,i,j} = \frac{\exp(z_{h,i,j})}{\sum_k \exp(z_{h,i,k}) + \exp(z'_h)}$$

This technique allows each query head to adjust its total attention scores to be not equal to 1, and even to be near 0.

---

Due to the employment of hybrid CSA and HCA, together with low-precision computation and storage, the attention module achieves remarkable efficiency. A mixed storage format is adopted for KV entries. BF16 precision for the RoPE dimensions, while FP8 precision for the remaining dimensions. Taking BF16 GQA-8 with a head dimension of 128 as the baseline, one of the common configurations of LLM attention, the KV cache size of DeepSeek-V4 series can be dramatically reduced to approximately **2% of that baseline** in the 1M-context setting.

![KV Cache Comparison](images/v4/kv_cache_2percent.png)

Moreover, even when compared with DeepSeek-V3.2, already an efficient baseline, DeepSeek-V4 series still exhibit substantial advantages in efficiency.

---

**Muon Optimizer.** The Muon optimizer is employed for the majority of modules due to its faster convergence and improved training stability. Algorithm 1 from the paper

![Algorithm 1, Muon for DeepSeek-V4](images/v4/muon_algorithm.png)

The AdamW optimizer is maintained for the embedding module, the prediction head module, the static biases and gating factors of mHC modules, and the weights of all RMSNorm modules. All other modules are updated with Muon. Weight decay is applied to Muon parameters, the Nesterov trick is used, and the Root Mean Square of the update matrix is rescaled for reutilization of the AdamW hyper-parameters.

**Hybrid Newton-Schulz Iterations.** For a given matrix $M$, each Newton-Schulz iteration performs

$$M_k = aM_{k-1} + b(M_{k-1}M_{k-1}^T)M_{k-1} + c(M_{k-1}M_{k-1}^T)^2 M_{k-1}$$

The hybrid Newton-Schulz performs 10 iterations over two distinct stages. During the first 8 steps, coefficients $(a,b,c) = (3.4445, -4.7750, 2.0315)$ drive rapid convergence, bringing the singular values close to 1. In the final 2 steps, coefficients $(a,b,c) = (2, -1.5, 0.5)$ stabilize the singular values precisely at 1.

With QK normalization in the architecture, the QK-Clip technique is no longer needed in the optimizer.

---

**Fine-Grained Communication-Computation Overlap in Expert Parallelism.**

![Figure 5, EP Communication-Computation Overlap](images/v4/ep_overlap.png)

MoE can be accelerated via Expert Parallelism (EP). However, EP requires complex inter-node communication and imposes substantial demands on interconnect bandwidth and latency. Each MoE layer can be decomposed mainly into four stages. Two communication-bound stages, Dispatch and Combine, and two computation-bound stages, Linear-1 and Linear-2. Within a single MoE layer, the total time of communication is less than that of the computation. Therefore, after fusing communication and computation into a unified pipeline, computation remains the dominant bottleneck, implying that the system can tolerate lower interconnect bandwidth without degrading end-to-end performance.

The experts are split and scheduled into waves. Each wave consists of a small portion of experts. As soon as all experts within the wave have completed their communication, computation can commence immediately without waiting for other experts. In steady state, computation of the current wave, token transfer for the next wave, and result sending of completed experts all proceed concurrently. The wave-based scheduling achieves a theoretical 1.92x speedup versus 1.42x for Comet. The CUDA-based mega-kernel implementation, named MegaMoE, has been open-sourced as a component of DeepGEMM.

**Observations and Proposals to Hardware Vendors**

- **Computation-Communication Ratio.** Full communication-computation overlap hinges on the computation-communication ratio rather than the bandwidth solely. They encourage future hardware designs to target such balance points rather than scale bandwidth unconditionally.
- **Power Budget.** Extreme kernel fusion drives compute, memory, and network to high load simultaneously, making power throttling a key performance limiter.
- **Communication Primitives.** A pull-based approach is adopted where each GPU actively reads data from remote GPUs. Future hardware with lower-latency cross-GPU signaling would make push viable and enable more natural communication patterns.
- **Activation Function.** They propose replacing SwiGLU with a low-cost element-wise activation that involves no exponential or division operations.

---

**TileLang**, a Domain-Specific Language for GPU kernel development that balances development productivity with runtime efficiency.

**Reducing Invocation Overhead with Host Codegen.** As accelerators continue to grow in performance, CPU-side orchestration overhead becomes increasingly prominent. Host Codegen moves most host-side logic into generated host code. CPU-side validation overhead drops from tens or hundreds of microseconds to less than one microsecond per invocation.

**SMT-Solver-Assisted Formal Integer Analysis.** TileLang kernels involve complex tensor index arithmetic that requires strong formal integer analysis. The Z3 SMT solver is integrated into TileLang's algebraic system, providing formal analysis capability for most integer expressions in tensor programs. They translate TileLang's integer expressions into Z3's quantifier-free non-linear integer arithmetic (QF_NIA). Under reasonable resource limits, Z3 elevates overall optimization performance while restricting compilation time overhead to just a few seconds. The impact is substantial across multiple passes, including vectorization, barrier insertion, and code simplification.

![SMT-Solver-Assisted Formal Analysis](images/v4/smt_solver.png)

---

**Batch Invariance and Determinism.**

Batch invariance ensures that the output of any given token remains bitwise identical, regardless of its position within a batch. Deterministic training is highly beneficial for debugging hardware or software issues.

**Attention.** To achieve batch invariance, the split-KV method cannot be used, which distributes the attention computation for a single sequence across multiple Stream Multiprocessors (SMs). However, abandoning this technique leads to severe wave-quantization problems. A dual-kernel strategy is developed. The first kernel computes the attention output for an entire sequence within a single SM, ensuring high throughput for fully occupied waves. The second kernel uses multiple SMs for a single sequence, to minimize the latency of the final partially-filled wave. The calculation path of the second kernel is carefully designed to ensure its accumulation order is the same as that of the first kernel, guaranteeing bitwise identity. The second kernel utilizes distributed shared memory within thread-block clusters, enabling high-speed data exchange across SMs. This dual-kernel method effectively confines the overhead of batch-invariant decoding to be negligible.

---

**FP4 Quantization-Aware Training.**

![FP4 QAT](images/v4/fp4_qat.png)

Quantization-Aware Training (QAT) is introduced during the post-training stage, enabling the model to adapt to the precision degradation introduced by quantization. FP4 (MXFP4) quantization is applied to two components. (1) MoE expert weights, which are a major source of GPU memory occupancy, and (2) the Query-Key (QK) path in the indexer of CSA, where QK activations are cached, loaded, and multiplied entirely in FP4, accelerating attention score computation in long-context scenarios.

For MoE expert weights, following the common practice of QAT, the FP32 master weights maintained by the optimizer are first quantized to FP4, then dequantized back to FP8 for computation. Notably, the FP4-to-FP8 dequantization is lossless. This is because FP8 (E4M3) has 2 additional exponent bits compared with FP4 (E2M1), offering a larger dynamic range. As long as the ratio between the maximum and minimum scale factors of the FP4 sub-blocks within each FP8 quantization block does not exceed a certain threshold, the fine-grained scale information can be fully absorbed by the extended dynamic range of FP8. They empirically verify that current weights satisfy this condition. In addition, the index scores are further quantized from FP32 to BF16, achieving a 2x speedup for the top-k selector, while preserving a 99.7% recall rate of KV entries.

During the inference and rollout phases of RL training, which do not involve backward passes, real FP4 quantized weights are used instead of simulated quantization. This ensures that model behavior during sampling is fully consistent with online deployment, while also reducing kernel memory loading for actual speedup and significantly lowering memory consumption.

---

**Efficient Implementation of Muon with ZeRO.**

![Efficient Muon with ZeRO](images/v4/muon_zero.png)

The Muon optimizer requires the full gradient matrix to compute parameter updates, which presents a challenge when combined with the Zero Redundancy Optimizer (ZeRO). Traditional ZeRO is designed for element-wise optimizers like AdamW, where a single parameter matrix can be partitioned and updated across multiple ranks.

For dense parameters, the maximum size of ZeRO parallelism is limited and a knapsack algorithm is used to assign parameter matrices to these ranks, ensuring each rank manages a roughly balanced load. For MoE parameters, each expert is optimized independently. All down projection matrices in SwiGLU of all experts across all layers are first flattened, followed by flattened up projection matrices and gate matrices. Then, the flattened vector is padded to ensure even distribution across all ranks without splitting any logically independent matrix.

Additionally, on each rank, consecutive parameters of identical shape are automatically merged, enabling batched execution of the Newton-Schulz iterations for better hardware utilization. The Newton-Schulz iterations in Muon remain stable when computed with BF16 matrix multiplications. Leveraging this, MoE gradients to be synchronized across data-parallel ranks are further quantized to BF16 precision in a stochastic rounding manner, halving the communication volume. To avoid accumulation errors introduced by low-precision adders, conventional tree- or ring-based reduce-scatter collectives are replaced with a two-phase approach. First, an all-to-all operation exchanges local gradients across ranks, and then each rank performs a local sum in FP32.

---

![Parallelism and KV Cache](images/v4/parallelism_kv.png)

**Contextual Parallelism for Long-Context Attention.** Conventional Context Parallelism (CP) partitions the sequence dimension. Training samples are packed from multiple sequences, and each sequence is compressed independently by a factor of $m$ (or $m'$), with any trailing tokens fewer than $m$ being discarded. Consequently, the compressed KV lengths are typically less than $\frac{s}{m}$ and vary across ranks. The compression requires $m$ consecutive KV entries, which may straddle the boundary between two neighboring CP ranks.

A two-stage communication approach is designed. In the first stage, each rank $i$ sends its last $m$ uncompressed KV entries to rank $i+1$. Then, rank $i+1$ compresses some of these received entries together with its local uncompressed KV entries. In the second stage, an all-gather operation across all CP ranks collects the locally compressed KV entries. Then, a fused select-and-pad operator reorganizes them into the full set of compressed KV entries.

**KV Cache Structure and Management.** The hybrid attention mechanism introduces multiple types of KV entries with different cache sizes and update rules. The lightning indexer introduces additional dimensions into the KV cache with embedding sizes distinct from the primary attention. The compression techniques in CSA and HCA reduce the sequence length by factors of $\frac{1}{m}$ and $\frac{1}{m'}$, thereby decreasing the overall KV cache size. As a result, KV cache sizes vary across different layers. In the compression branch, one KV entry is generated for every $m$ tokens. When the number of remaining tokens is insufficient for compression, all pending tokens and their associated hidden states must be retained in a buffer until the compression operation can be executed.

The KV cache is organized into two primary components. A classical KV cache for CSA/HCA, and a state cache for SWA and unready-for-compression tokens. In the state cache, each request is assigned a fixed-size cache block. In the classical KV cache, multiple blocks are allocated per request. Each cache block covers $\text{lcm}(m, m')$ original tokens.

For on-disk KV cache storage, three strategies are implemented for SWA KV entries, each offering a different trade-off between storage overhead and computational redundancy. Full SWA Caching (stores complete SWA KV entries for all tokens), Periodic Checkpointing (checkpoints SWA KV entries every $p$ tokens), and Zero SWA Caching (does not store any SWA KV entries, leveraging cached CSA and HCA KV entries to recompute the last $n_{\text{win}} \cdot L$ tokens).

**Activation Checkpointing.** A tensor-level activation checkpointing mechanism with automatic differentiation support is implemented. Developers only need to implement the forward pass and selectively annotate individual tensors for automatic checkpointing and recomputation. The framework leverages TorchFX to trace the full computation graph. For each annotated tensor, it performs a backward traversal to identify the minimal subgraph required for its recomputation.

---

**Pre-Training Data.** On top of the pre-training data of DeepSeek-V3, a more diverse and higher-quality training corpus with longer effective contexts is constructed. For web-sourced data, filtering strategies remove batched auto-generated and templated content, thereby mitigating the risk of model collapse. Mathematical and programming corpora still remain core components. Coding capabilities are further enhanced by incorporating agentic data during the mid-training phase. For multilingual data, a larger corpus is built, improving capture of long-tail knowledge across different cultures. Particular emphasis is placed on long-document data curation, prioritizing scientific papers, technical reports, and other materials that reflect unique academic values. The pre-training corpus comprises more than 32T tokens.

![Data Construction](images/v4/data_construction.png)

For tokenization, on top of the DeepSeek-V3 tokenizer, a few special tokens are introduced for context construction, and the vocabulary size remains 128K.

![Quick Instruction Special Tokens](images/v4/special_tokens.png)

---

**Pre-Training Setups.**

DeepSeek-V4-Flash. 43 Transformer layers, hidden dimension $d = 4096$. First two layers use pure sliding window attention; subsequent layers interleave CSA and HCA. CSA compression rate $m = 4$, attention top-k = 512. HCA compression rate $m' = 128$. Each MoE layer consists of 1 shared expert and 256 routed experts, with 6 experts activated per token. Trained on 32T tokens. The Muon optimizer is employed for the majority of parameters. AdamW hyper-parameters are $\beta_1 = 0.9, \beta_2 = 0.95, \varepsilon = 10^{-20}$, weight decay = 0.1. Muon momentum = 0.95, weight decay = 0.1, RMS of each update matrix rescaled to 0.18. Learning rate warmed up in 2000 steps, maintained at $2.7 \times 10^{-4}$, then decayed to $2.7 \times 10^{-5}$ following a cosine schedule. Training starts with a sequence length of 4K, gradually extended to 16K, 64K, and 1M. Dense attention used for the first 1T tokens, then an indexer warmup stage, then sparse attention for the rest of training. MTP loss weight set to 0.3, reduced to 0.1 upon the start of learning rate decay.

DeepSeek-V4-Pro. 61 Transformer layers, hidden dimension $d = 7168$. First two layers use HCA; subsequent layers interleave CSA and HCA. CSA compression rate $m = 4$, attention top-k = 1024. HCA compression rate $m' = 128$. Each MoE layer consists of 1 shared expert and 384 routed experts, with 6 experts activated per token. Trained on 33T tokens. Peak learning rate $2.0 \times 10^{-4}$, end learning rate $2.0 \times 10^{-5}$. Compared with DeepSeek-V4-Flash, DeepSeek-V4-Pro starts with a longer stage of dense attention.

![DeepSeek-V4-Pro Training Setup](images/v4/training_setup_pro.png)

For auxiliary-loss-free load balancing, the bias update speed is set to 0.001. The balance loss weight is set to 0.0001. The MTP loss weight is set to 0.3 for most of the training, and to 0.1 upon the start of learning rate decay.

---

**Mitigating Training Instability.** Training trillion-parameter MoE models presents significant stability challenges, and DeepSeek-V4 series are no exception. Notable instability challenges were encountered during training. While simple rollbacks could temporarily restore the training state, they proved inadequate as a long-term solution because they do not prevent the recurrence of loss spikes. Empirically, the occurrence of spikes is consistently tied to outliers in the MoE layers, and the routing mechanism itself appears to exacerbate the emergence of these outliers.

**Anticipatory Routing.**

![Anticipatory Routing](images/v4/anticipatory_routing.png)

Decoupling the synchronous updates of the backbone network and the routing network significantly improves training stability. At step $t$, the current network parameters $\theta_t$ are used for feature computation, but the routing indices are computed and applied using the historical network parameters $\theta_{t - \Delta t}$. In practice, to circumvent the overhead of loading model parameters twice, the data for step $t$ is fetched in advance at step $t - \Delta t$. Routing indices are "anticipatorily" computed and cached to be used later at step $t$. An automatic detection mechanism triggers a short rollback and activates Anticipatory Routing exclusively when a loss spike occurs; after operating in this mode for a certain period, the system reverts to standard training.

**SwiGLU Clamping.**

![SwiGLU Clamping](images/v4/swiglu_clamping.png)

Applying SwiGLU clamping effectively eliminates outliers and substantially aids in stabilizing the training process, without compromising performance. Throughout training of both models, the linear component of SwiGLU is clamped to the range of $[-10, 10]$, while capping the upper bound of the gate component at 10.

---

**Product-Level Details.**

**Tool-Call Schema.** DeepSeek-V4 series introduce a new tool-call schema that employs a special `|DSML|` token and utilizes an XML-based format for tool invocations. The XML format effectively mitigates escaping failures and reduces tool-call errors, providing a more robust interface for model-tool interactions.

**Interleaved Thinking.** DeepSeek-V4 series manage thinking tokens differently depending on the context.

- **Tool-Calling Scenarios.** All reasoning content is fully preserved throughout the entire conversation. Unlike DeepSeek-V3.2, which discarded thinking traces upon each new user turn, DeepSeek-V4 series retain the complete reasoning history across all rounds, including across user message boundaries. This allows the model to maintain a coherent, cumulative chain of thought over long-horizon agent tasks.
- **General Conversational Scenarios.** The original strategy is preserved. Reasoning content from previous turns is discarded when a new user message arrives, keeping the context concise for settings where persistent reasoning traces provide limited benefit.

Agent frameworks that simulate tool interactions via user messages may not trigger the tool-calling context path and thus may not benefit from enhanced reasoning persistence. Non-think models are recommended for such architectures.

**Quick Instruction.** In chatbot scenarios, a number of auxiliary tasks (e.g., determining whether to trigger a web search, intent recognition) must be executed before generating the response. Conventionally, these tasks are handled by a separate small model, requiring redundant prefilling since it cannot reuse the existing KV cache. A set of dedicated special tokens is appended directly to the input sequence, where each token corresponds to a specific auxiliary task. By directly reusing the already-computed KV cache, this mechanism completely avoids redundant prefilling and significantly reduces the user-perceived time-to-first-token (TTFT).

---

**Post-Training Pipeline.**

![Post-Training Pipeline](images/v4/post_training.png)

Although the training pipeline largely mirrored that of DeepSeek-V3.2, a critical methodological substitution was made. **The mixed Reinforcement Learning (RL) stage was entirely replaced by On-Policy Distillation (OPD).**

**Specialist Training.** Each model is sequentially optimized through an initial fine-tuning phase and subsequent Reinforcement Learning guided by domain-specific prompts and reward signals. For the RL stage, the Group Relative Policy Optimization (GRPO) algorithm is implemented. Distinct specialist models are trained under divergent RL configurations to facilitate models optimized for varying reasoning capacities.

- **Non-think.** Fast, intuitive responses based on habits or simple rules.
- **Think High.** Conscious logical analysis, slower but more accurate.
- **Think Max.** Push reasoning to its fullest extent. Slow but powerful.

For the Think Max mode, a specific instruction is prepended to the beginning of the system prompt.

![Think Max Injected Instruction](images/v4/think_max_prompt.png)

> *"Reasoning Effort. Absolute maximum with no shortcuts permitted. You MUST be very thorough in your thinking and comprehensively decompose the problem to resolve the root cause, rigorously stress-testing your logic against all potential paths, edge cases, and adversarial scenarios. Explicitly write out your entire deliberation process, documenting every intermediate step, considered alternative, and rejected hypothesis to ensure absolutely no assumption is left unchecked."*

**Generative Reward Model.** To address hard-to-verify tasks, rubric-guided RL data is curated and a Generative Reward Model (GRM) is employed to evaluate policy trajectories. RL optimization is applied directly to the GRM itself. In this paradigm, the actor network natively functions as the GRM, enabling the joint optimization of the model's evaluative (judging) proficiency alongside its standard generative capabilities. By unifying these roles, the model's internal reasoning capabilities are inherently fused into its evaluative process, resulting in highly robust scoring. This approach achieves superior performance with only a minimal set of diverse human annotations, as the model leverages its own logic to generalize across complex tasks.

![Generative Reward Model](images/v4/grm_opd.png)

**On-Policy Distillation.** After training multiple domain-specific experts, multi-teacher OPD is the primary technique for merging expert capabilities into the final model. Given a set of $N$ expert models $\{\pi_{E_1}, \pi_{E_2}, \ldots, \pi_{E_N}\}$, the OPD objective function is

$$\mathcal{L}_{\text{OPD}}(\theta) = \sum_{i=1}^{N} w_i \cdot D_{\text{KL}}\left(\pi_\theta \| \pi_{E_i}\right)$$

![OPD Objective](images/v4/opd_objective.png)

Computing the reverse KL loss requires sampling training trajectories from the student $\pi_\theta$ to maintain on-policy learning. The knowledge from physically distinct expert weights is consolidated into a unified parameter space via logits-level alignment, practically circumventing the performance degradation often encountered in traditional weight-merging or mixed RL techniques. More than ten teacher models covering various domains are employed to distill a single student model.

Full-vocabulary logit distillation is adopted. Preserving the complete logit distribution in calculating reverse KL loss yields more stable gradient estimates and ensures faithful distillation of the teachers' knowledge. For efficiency, all teacher weights are offloaded to centralized distributed storage and loaded on demand. Only the last-layer teacher hidden states are cached, and the full logits are reconstructed on the fly. This design incurs negligible recomputation overhead while completely circumventing the memory burden associated with explicit logits materialization.

---

**Long-Context Evaluation.** DeepSeek-V4-Pro outperforms Gemini-3.1-Pro on the MRCR task, which measures in-context retrieval, but remains behind Claude Opus 4.6. Retrieval performance remains highly stable within a 128K context window. While a performance degradation becomes visible beyond the 128K mark, the model's retrieval capabilities at 1M tokens remain remarkably strong compared to both proprietary and open-source counterparts. On CorpusQA, which is similar to real scenarios, the evaluation results also indicate that DeepSeek-V4-Pro is better than Gemini-3.1-Pro.

**Reasoning.** DeepSeek-V4-Pro-Max outperforms all prior open models across reasoning benchmarks, and matches state-of-the-art closed models on many metrics. On the Codeforces leaderboard, DeepSeek-V4-Pro-Max currently ranks 23rd among human candidates. Nevertheless, its performance falls marginally short of GPT-5.4 and Gemini-3.1-Pro, suggesting a developmental trajectory that trails state-of-the-art frontier models by approximately 3 to 6 months.

**Agent.** On public benchmarks, DeepSeek-V4-Pro-Max is on par with leading open-source models, such as Kimi-K2.6 and GLM-5.1, but slightly worse than frontier closed models. In internal evaluation, DeepSeek-V4-Pro-Max outperforms Claude Sonnet 4.5 and approaches the level of Opus 4.5.

---

In pursuit of extreme long-context efficiency, DeepSeek-V4 series adopted a bold architectural design. In future iterations, they will carry out more comprehensive and principled investigations to distill the architecture down to its most essential designs, making it more elegant without sacrificing performance. Although Anticipatory Routing and SwiGLU Clamping have been proven effective in mitigating training instabilities, their underlying principles remain insufficiently understood.

Beyond the MoE and sparse attention architecture, they will also proactively explore model sparsity along new dimensions, such as more sparse embedding modules, to further improve computational and memory efficiency without compromising capability. They will also continuously investigate low-latency architectures and system techniques to make long-context deployment and interaction more responsive. They recognize the importance and practical value of long-horizon, multi-round agentic tasks, and will continue to iterate and explore in this direction. They are also working on incorporating multimodal capabilities.

DeepSeek-V4 series achieve a dramatic leap in long-sequence efficiency. The architectural innovations, together with extensive infrastructure optimization, enable efficient native support for million-token contexts and establish a necessary foundation for future test-time scaling, long-horizon tasks, and emerging paradigms such as online learning. They believe DeepSeek-V4 series usher in a new era of million-length contexts for open models and pave the way toward better efficiency, scale, and intelligence.

Model weights and inference code are at [huggingface.co/deepseek-ai](https://huggingface.co/collections/deepseek-ai/deepseek-v4).
