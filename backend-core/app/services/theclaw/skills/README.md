# The Claw Skills

Skills are markdown contracts. Each skill lives in its own folder with a `SKILL.md` file.

Folders are for human organization only (not deterministic routing):
- `core`
- `ppc`
- `catalog`
- `p&l`
- `replenishment`
- `wbr`

Routing model:
- Runtime sends one flat `<available_skills>` menu to the router LLM.
- The model selects the best skill by semantic fit (or `none`).
- Category folders do not pre-filter skills at runtime.
