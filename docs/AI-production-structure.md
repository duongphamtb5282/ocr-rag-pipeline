fi

eee

production-ai-—app/

... app/

main. py

config. py

models.py

Dockerfile

components/ie hybrid\_retriever. py

reranker.py

services/

rag\_pipeline. py

semantic\_cache. py

conversation. py

query\_rewriter. py

query\_router. py

prompts/iz templates.py

registry.py

agents/

document\_grader. py query\_decomposer. py adaptive\_router.py tools/vector\_search.py

web\_search.py

code\_search.py security/

input\_guard.py

content\_filter.py

-output\_Tilter. py H— eval uation/

golden\_dataset.json

offline\_eval.py

online\_monitor.py

eval\_results/

H— obse rvability/

precelepy

feedback. py

(ee) ugce er. py

.. data

raw/

processed/

index\_config/

H— scri pts/

seed. py

i— migrate. py

healthcheck. py

H— fron tend/

Fystatic/0) ..

requirements. txt

pocke .....

.. test S

test\_retrieval. py

test\_cache. py

- test\_routing.py

.. architecture.md

.. api-reference.md

- deployment.md

H— .Cla We(9

rules/

code-style.md

testing.md

.. CLAUDE.md

.. AGENTS.md

. docker-compose. yml

- pyere ject.toml
- README.md

fe)geye[Oledlo)nrer-]br=]0)0)

FastAPI entry, config, schemas, containerized Custom retrieval: hybrid search + reranking

Core business logic: pipeline, cache, memory, rewriting, routing

Versioned,type-specific,hot-swappable

Intelligence layer: self-correcting retrieval, LLM-driven source selection

Pluggable tool definitions

Three guard layers: input, content, output Golden test set, offline + online pipelines,

tracked history

Per-stage tracing, feedback capture, cost breakdown

Raw > processed > index config Seed, migrate, healthcheck

UI, containerized separately

Retrieval, cache, routing tests. CI-ready. Architecture, API ref, deployment guide

AI coding agent context, rules, project memory
