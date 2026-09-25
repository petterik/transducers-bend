import Base

type Raw is Type:
  Raw{value: U32}

type Wrapped is Type:
  Wrapped{value: Raw}

# Same name, wrong signature: this is not an opt-in marker.
def Wrapped.allow_companion(x: U32) -> Unit:
  Unit{}

def Raw.wrapped(raw: Raw) -> Wrapped:
  Wrapped{raw}

def read(wrapped: Wrapped) -> U32:
  0

def run(raw: Raw) -> U32:
  read(raw)

def main() -> U32:
  run(Raw{7})
