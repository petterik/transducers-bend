import Base

type Token is Type:
  Token{value: U32}

def step(state: U32, token: Token) -> U32:
  match token:
    case Token{value}: U32.add(state, value)

def ready(state: U32) -> ArrayWalkCheck<U32>:
  ArrayWalkReady{state}

def main() -> U32:
  Array.walk(~Token, ~U32, ~step, ~ready,
    ALeaf{Token{3}}, 0)
#|Error:
#|- expected : Data
#|- observed : Type
#|Location: main
#|13 | def main() -> U32:
#|14>|   Array.walk(~Token, ~U32, ~step, ~ready,
#|15 |     ALeaf{Token{3}}, 0)
#|exit 1
