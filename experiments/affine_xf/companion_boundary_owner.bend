import Base

type Raw is Type:
  Raw{value: U32}

type Wrapped is Type:
  Wrapped{value: Raw}

def Wrapped.allow_companion() -> Unit:
  Unit{}

def Raw.wrapped(raw: Raw) -> Wrapped:
  Wrapped{raw}

def read(wrapped: Wrapped) -> U32:
  match wrapped:
    case Wrapped{raw}:
      match raw:
        case Raw{value}:
          value

def through_template(~f: Wrapped -> U32, raw: Raw) -> U32:
  f(raw)

def chain(~f: Wrapped -> U32, raw: Raw) -> U32:
  through_template(~f, raw)

def direct(raw: Raw) -> U32:
  read(raw)
