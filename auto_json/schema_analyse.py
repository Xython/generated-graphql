import typing as t
import warnings

NoneType = None.__class__

T = t.TypeVar('T')


class AutoJsonMeta(type):
    def __new__(mcs, name, bases, ns: dict):
        if ns.get('_root', False):
            return super().__new__(mcs, name, bases, ns)
        bases = tuple(filter(lambda it: AutoJson is not it, bases))

        ret = type(name, (*bases, Json), ns)
        SchemaMonitor.register(ret)

        annotations = ns.get('__annotations__', [])

        def __init__(self, **kwargs):
            if not kwargs:
                return
            for each in annotations:

                setattr(self, each, kwargs[each])

        template_format = f'{ret.__name__}({{}})'.format

        def __repr__(self):
            return template_format(', '.join(
                f'{each}={getattr(self, each)!r}' for each in annotations))

        ret.__init__ = __init__
        ret.__repr__ = __repr__
        return ret


class Json:
    pass


class AutoJson(metaclass=AutoJsonMeta):
    _root = True

    def __init__(self, *args, **kwargs):
        raise TypeError

    def to_dict(self) -> dict:
        raise TypeError

    def to_bson(self) -> bytes:
        raise TypeError

    def to_json(self) -> bytes:
        raise TypeError

    @classmethod
    def from_dict(cls: t.Type[T], data: dict) -> T:
        raise TypeError


class Spec:
    pass


class Named(Spec, t.NamedTuple):
    typ: type


class ForwardRef(Spec, t.NamedTuple):
    """
    to resolve cross references
    class S:
        a: A
        s: S
    
    class A:
        i: int
    """
    name: str


class Concrete(Spec, t.NamedTuple):
    """
    str, int, float, null
    """
    typ: type


NoneConcrete = Concrete(NoneType)


class Optional(Spec, t.NamedTuple):
    typ: Spec


class Union(Spec, t.NamedTuple):
    args: t.List[Spec]


class List(Spec, t.NamedTuple):
    elem: Spec


class Dict(Spec, t.NamedTuple):
    key: Spec
    value: Spec


class SchemaMonitor:
    # schemas: qualname -> (type, [(field_name, field_type_spec)])
    schemas: t.Dict[str, t.Tuple[type, t.List[t.Tuple[str, Spec]]]] = {}
    # methods: qualname -> (from_dict, to_dict, query)
    methods: t.Dict[str, t.List[t.Callable]]

    def __init__(self):
        raise TypeError("Monitor is a singleton.")

    @classmethod
    def remove(cls, typ: t.Union[str, type]):

        subscript = typ
        if isinstance(subscript, type):
            subscript = subscript.__qualname__

        del cls.schemas[subscript]

    @classmethod
    def register(cls, typ: type):
        """
        :param typ: must be checked to contains __annotations__
        :return:
        """
        qualname = typ.__qualname__
        if qualname in cls.schemas:
            warnings.warn(f"Overwriting json type schema {qualname!r}.")

        cls.schemas[typ.__qualname__] = typ, [
            (k, describe(t)) for k, t in typ.__annotations__.items()
        ]

    @classmethod
    def resolve(cls, strict=False):
        for _, (ty, fields) in cls.schemas.items():
            for i in range(len(fields)):
                attr, field = fields[i]
                fields[i] = attr, backref(field, strict=strict)


def backref(spec: Spec, strict) -> Spec:
    def _backref(_):
        return backref(_, strict)

    if isinstance(spec, (Optional, Concrete, Named)):
        return spec

    if isinstance(spec, ForwardRef):
        type_and_fields = SchemaMonitor.schemas.get(spec.name)
        if type_and_fields:
            return Named(type_and_fields[0])
        if not strict:
            return spec
        raise TypeError(f'forward ref: {spec}.')

    if isinstance(spec, List):
        return List(_backref(spec.elem))

    if isinstance(spec, Dict):
        key = _backref(spec.key)
        value = _backref(spec.value)
        return Dict(key, value)

    if isinstance(spec, Union):

        return Union(list(map(_backref, spec.args)))

    raise TypeError(spec)


def describe(ty: t.Union[str, t.Type]) -> Spec:
    if isinstance(ty, str):
        return ForwardRef(ty)

    if ty in (int, float, str, NoneType):
        return Concrete(ty)

    if hasattr(ty, '__origin__'):
        args: list = []

        def is_origin(typ):
            return ty.__origin__ is typ and (args.extend(
                getattr(ty, '__args__')) or True)

        if is_origin(t.List):
            e_ty, = args
            return List(describe(e_ty))
        elif is_origin(t.Union):
            args = list(map(describe, args))

            if len(args) is 2 and NoneConcrete in args:
                e_ty = args[args[0] == NoneConcrete]
                return Optional(e_ty)
            return Union(args)
        elif is_origin(t.Dict):
            key, value = map(describe, args)
            return Dict(key, value)
    if hasattr(ty, '__forward_arg__'):
        return describe(getattr(ty, '__forward_arg__'))

    assert issubclass(
        ty, Json), TypeError(f"expected Json type, got {ty.__qualname__!r}.")

    return Named(ty)
