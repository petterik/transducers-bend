# transduce-bend

A proposed library for composable, efficient data transformations in Bend.

Compose pure transformations such as map, filter, and take, then execute them with `transduce` or collect their outputs with `into_list`. The design uses compile-time operation templates and explicit owned runtime state to avoid intermediate collections between stages.

This repository currently contains the design, not an implementation. Examples in the design use conceptual notation rather than a finalized Bend API.

- [Library design](DESIGN.md)
- [Confidence review and experimental evidence](CONFIDENCE.md)
