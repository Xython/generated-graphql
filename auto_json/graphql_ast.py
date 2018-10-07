"""
ast 层面的graphql优化:

重点是inline, 作用:

    1. 内联减少函数调用
    2. 对比python前端实现的naive版本,
       ast generated函数可以内联非自递归的所有函数,
       将全局变量固定到局部被多个内联函数共用。

"""
# from astpretty import pprint
# from rbnf.py_tools.unparse import Unparser

from .schema_analyse import *
import ast


class CollectLocal(ast.NodeVisitor):
    def __init__(self):
        self.names = set()

    def _visit_name(self, node: ast.Name):
        ident: str = node.id

        if ident.startswith('_'):
            self.names.add(ident)

    visit_Name = _visit_name


class BlockLevel:
    def __init__(self, var_name='', id_=0):
        self.id = id_
        self.var_name = var_name

    def var(self, var_name: str):
        return BlockLevel(var_name, self.id)

    def let(self):
        return BlockLevel(id_=self.id + 1)

    def to_name(self):
        return f'b_{self.var_name}_{self.id}'


def ast_isinstance(var: BlockLevel, primitive: type):
    return ast.Call(
        ast_name('_isinstance'),
        [ast_name(var.to_name()),
         ast_name('_' + primitive.__name__)], [])


def ast_assign(lhs: BlockLevel, rhs: t.Union[BlockLevel, ast.expr]):
    rhs = ast.Name(rhs.to_name(), ast.Load()) if isinstance(
        rhs, BlockLevel) else rhs

    return ast.Assign([ast.Name(lhs.to_name(), ast.Store())], rhs)


def ast_name(var: t.Union[BlockLevel, str], is_lhs=False):
    if isinstance(var, BlockLevel):
        var = var.to_name()
    return ast.Name(var, (ast.Store if is_lhs else ast.Load)())


def ast_call(func, args):
    return ast.Call(func, args, [])


def ast_attr(value, attr: str, is_lhs=False):
    ctx = (ast.Store if is_lhs else ast.Load)()
    return ast.Attribute(value, attr, ctx)


def ast_subscript(value, attr: str, is_lhs=False):
    ctx = (ast.Store if is_lhs else ast.Load)()
    return ast.Subscript(value, ast.Str(attr), ctx)


def ast_raise_type_err(msg: str, data_var: BlockLevel):
    return ast.Raise(
        ast_call(
            ast_name('_TypeError'),
            [ast_call(ast_attr(ast.Str(msg), 'format'), [ast_name(data_var)])
             ]), None)


def generate_method_maker() -> t.Tuple[t.List[type], ast.Module]:
    def make_match_from_spec(
            spec: Spec,
            block: BlockLevel = BlockLevel(),
            recur=(),
    ) -> t.List[ast.AST]:
        def _make_match_from_spec(spec_, reg_=block):
            return make_match_from_spec(spec_, reg_, (*recur, spec_))

        if recur.count(spec) is 2 and isinstance(spec, Named):
            # avoid recursive expanding
            return [
                ast_assign(
                    block.var('ret'),
                    ast_call(
                        ast_name('make_' + spec.typ.__name__),
                        [ast_name(block)]))
            ]

        if isinstance(spec, ForwardRef):
            raise TypeError

        if isinstance(spec, Concrete):
            typ = spec.typ
            assign_suites = [ast_assign(block.var('ret'), block)]
            if typ is object:
                return assign_suites
            else:
                return [
                    ast.If(
                        ast_isinstance(block, typ), assign_suites, [
                            ast_raise_type_err(
                                'expected an instance of ' + repr(typ) +
                                ', got {!r}.', block)
                        ])
                ]

        if isinstance(spec, List):
            lst_var = block.var('ret')
            append_var = block.var('append')
            iter_block = block.let()

            method_ast_suites = _make_match_from_spec(spec.elem, iter_block)
            return [
                ast_assign(lst_var, ast.List([], ast.Load())),
                ast_assign(append_var, ast_attr(ast_name(lst_var), 'append')),
                ast.For(
                    target=ast_name(iter_block, is_lhs=True),
                    iter=ast_name(block),
                    body=[
                        *method_ast_suites,
                        ast.Expr(
                            ast_call(
                                ast_name(append_var),
                                [ast_name(iter_block.var('ret'))]))
                    ],
                    orelse=[])
            ]

        if isinstance(spec, Union):
            raise NotImplementedError

        if isinstance(spec, Dict):

            dict_var = block.var('ret')
            dict_add_var = dict_var.var('append')

            key_var = block.var('key')
            value_var = block.var('value')

            key_block = block.let().var('key')
            value_block = block.let().var('value')

            key_match, value_match = _make_match_from_spec(
                spec.key, key_block), _make_match_from_spec(
                    spec.value, value_block)

            return [
                ast_assign(dict_var, ast.Dict([], [])),
                ast_assign(dict_add_var,
                           ast_attr(ast_name(dict_var), '__setitem__')),
                ast.For(
                    target=ast.Tuple([
                        ast_name(key_block, is_lhs=True),
                        ast_name(value_block, is_lhs=True)
                    ], ast.Store()),
                    iter=ast_call(ast_attr(ast_name(block), 'items'), []),
                    body=[
                        *key_match,
                        ast_assign(key_var, key_block.var('ret')),
                        *value_match,
                        ast_assign(value_var, value_block.var('ret')),
                        ast.Expr(
                            ast_call(
                                ast_name(dict_add_var),
                                [ast_name(key_var),
                                 ast_name(value_var)]))
                    ],
                    orelse=[])
            ]

        if isinstance(spec, Optional):
            match_ast_suites = _make_match_from_spec(spec.typ)
            return [
                ast.If(
                    test=ast_name(block),
                    body=match_ast_suites,
                    orelse=[
                        ast_assign(block.var('ret'), ast.NameConstant(None))
                    ])
            ]

        if isinstance(spec, Named):
            named_type = spec.typ
            field_block = block.let()
            cls_instance_var = block.var('ret')
            data_field_getter_var = block.var('append')

            def make_match_for_attr(attr: str, field_spec: Spec):
                if isinstance(field_spec, ForwardRef):
                    raise TypeError
                else:
                    extract_suites = _make_match_from_spec(
                        field_spec, field_block)
                    return [
                        ast_assign(
                            field_block,
                            ast_call(
                                ast_name(data_field_getter_var),
                                [ast.Str(attr)])), *extract_suites,
                        ast.Assign([
                            ast_attr(
                                ast_name(cls_instance_var), attr, is_lhs=True)
                        ], ast_name(field_block.var('ret')))
                    ]

            _, fields = SchemaMonitor.schemas[named_type.__qualname__]
            fields_making = list(map(make_match_for_attr, *zip(*fields)))
            return [
                ast_assign(cls_instance_var,
                           ast_call(ast_name('_' + named_type.__name__), [])),
                ast_assign(data_field_getter_var,
                           ast_attr(ast_name(block), 'get')),
                *sum(fields_making, [])
            ]
        else:
            raise TypeError(spec)

    def make_function_ast(ty: type):

        nodes = make_match_from_spec(Named(ty))
        b = BlockLevel()
        ret = ast.FunctionDef(
            name='make_' + ty.__name__,
            args=ast.arguments(
                args=[ast.arg(b.to_name(), None)],
                vararg=None,
                kwonlyargs=[],
                kwarg=None,
                kw_defaults=[],
                defaults=[]),
            body=[*nodes, ast.Return(ast_name(b.var('ret')))],
            decorator_list=[],
            returns=None)

        ast.fix_missing_locations(ret)
        return ret

    types = [a[0] for a in SchemaMonitor.schemas.values()]

    fns = list(map(make_function_ast, types))

    exports = ast.Return(
        ast.Dict(*map(
            list,
            zip(*[(ast.Str(each.__qualname__),
                   ast_name('make_' + each.__name__)) for each in types]))))

    closure = ast.FunctionDef(
        name='make',
        args=ast.arguments(
            args=[],
            vararg=None,
            kwonlyargs=[],
            kwarg=None,
            kw_defaults=[],
            defaults=[]),
        body=[*fns, exports],
        decorator_list=[],
        returns=None)

    # optimize name loading to avoid looking up from global context.
    collected = CollectLocal()
    collected.visit(closure)
    local_bindings = collected.names

    closure.body = [
        *[
            ast.Assign([ast_name(name, is_lhs=True)], ast_name(name[1:]))
            for name in local_bindings
        ], *closure.body
    ]

    ast.fix_missing_locations(closure)
    # pprint(closure)
    mod = ast.Module([closure])
    return types, mod


def generate():
    types, mod = generate_method_maker()
    # Unparser(mod)
    ctx = {t.__name__: t for t in types}
    exec(compile(mod, "<generated module>", 'exec'), ctx)
    fn_dict: dict = ctx['make']()
    for qualname, fn in fn_dict.items():
        ty, _ = SchemaMonitor.schemas[qualname]
        setattr(ty, 'from_dict', staticmethod(fn))
