from .schema_analyse import *


class _RefFunc:
    def __call__(self, arg1):
        raise TypeError


def ref_func(name='RefFunc') -> _RefFunc:
    return type(name, (), {})()


def identity(x):
    return x


def generate():
    def make_from_spec(spec: Spec, recur=None,
                       trace='') -> t.Tuple[_RefFunc, _RefFunc]:
        def _make_from_dict_from_spec(spec_):
            return make_from_spec(
                spec_,
                recur,
                trace=repr(spec_) if not trace else f'{trace}.{repr(spec_)}')

        recur = recur or {}
        methods = recur.get(spec)

        if methods:
            return methods

        ref_from_dict, ref_to_dict = recur[spec] = ref_func(
            trace + '-fromdict'), ref_func(trace + 'todict')

        if isinstance(spec, ForwardRef):
            raise TypeError

        elif isinstance(spec, Concrete):
            typ = spec.typ

            to_dict = identity

            if typ is object:
                from_dict = identity
            else:

                def from_dict(data):
                    if isinstance(data, typ):
                        return data
                    raise TypeError(
                        f'expected an instance of {typ!r}, got {data}.')

        elif isinstance(spec, List):
            elem_from_dict, elem_to_dict = _make_from_dict_from_spec(spec.elem)

            def from_dict(data):
                return [elem_from_dict(each) for each in data]

            if elem_to_dict is not identity:

                def lst_to_dict(obj):

                    return [elem_to_dict(each) for each in obj]

                to_dict = lst_to_dict
            else:
                to_dict = list

        elif isinstance(spec, Union):
            raise NotImplementedError

        elif isinstance(spec, Dict):
            (key_from_dict,
             key_to_dict), (value_from_dict,
                            value_to_dict) = _make_from_dict_from_spec(
                                spec.key), _make_from_dict_from_spec(
                                    spec.value)

            def from_dict(data):
                return {
                    key_from_dict(k): key_from_dict(v)
                    for k, v in data.items()
                }

            if key_to_dict is identity and value_to_dict is identity:
                to_dict = identity
            else:

                def to_dict(obj):
                    return {
                        key_to_dict(k): value_to_dict(v)
                        for k, v in obj.items()
                    }

        elif isinstance(spec, Optional):
            elem_from_dict, elem_to_dict = _make_from_dict_from_spec(spec.typ)

            def from_dict(data):
                return elem_from_dict(data) if data else None

            def opt_to_dict(obj):
                return elem_to_dict(obj) if obj else None

            to_dict = opt_to_dict

        elif isinstance(spec, Named):
            named_type = spec.typ

            def make_from_dict_for_attr(attr: str, field_spec: Spec):

                if isinstance(field_spec, ForwardRef):
                    raise TypeError

                elif isinstance(field_spec, Concrete):
                    typ_ = field_spec.typ
                    if typ_ is object:

                        def bind_obj(obj, data):
                            data = data.get(attr)
                            if isinstance(data, typ_):
                                setattr(obj, attr, data)
                                return
                            raise TypeError(
                                f'expected an instance of {typ_!r}, got ({data}).'
                            )
                    else:

                        def bind_obj(obj, data):
                            setattr(obj, attr, data.get(attr))

                    def add_dict(obj, data):
                        data[attr] = getattr(obj, attr, None)
                else:
                    extract, field_to_dict = _make_from_dict_from_spec(
                        field_spec)

                    def bind_obj(obj, data):
                        setattr(obj, attr, extract(data.get(attr)))

                    def add_dict(obj, data):
                        data[attr] = field_to_dict(getattr(obj, attr))

                return bind_obj, add_dict

            _, fields = SchemaMonitor.schemas[named_type.__qualname__]

            binds, adds = zip(*map(make_from_dict_for_attr, *zip(*fields)))

            def from_dict(data):
                obj = named_type()
                for bind in binds:
                    bind(obj, data)
                return obj

            def cls_to_dict(obj):
                ret = {}
                for add in adds:
                    add(obj, ret)
                return ret

            to_dict = cls_to_dict
        else:
            raise TypeError(spec)

        ref_from_dict.__class__.__call__ = staticmethod(from_dict)
        ref_to_dict.__class__.__call__ = staticmethod(to_dict)
        return ref_from_dict, ref_to_dict

    for ty, _ in SchemaMonitor.schemas.values():
        ref_from_dict, ref_to_dict = make_from_spec(Named(ty))
        setattr(ty, 'from_dict', ref_from_dict.__class__.__call__)
        setattr(ty, 'to_dict', ref_to_dict.__class__.__call__)
