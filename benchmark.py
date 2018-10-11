from auto_json.schema_analyse import *
from auto_json.graphql_naive import generate as naive_generate
from auto_json.graphql_ast import generate as ast_generate
from pprint import pprint
from timeit import timeit


class S(AutoJson):
    a: int
    b: 'A'


class A(AutoJson):
    c: float
    s: t.Optional[S]


SchemaMonitor.resolve(strict=True)
pprint(SchemaMonitor.schemas)
naive_generate()
data = {'c': 1.0, 's': {'a': 1, 'b': {'c': 1.90, 's': None}}}
naive_make_A = A.from_dict
a = naive_make_A(data)
print(a)

ast_generate(use_cython=True)
ast_make_A = A.from_dict
a = ast_make_A(data)
print(a)

ctx = {'data': data}

print('==================')
print('naive version costs: ',
      timeit('fn(data)', number=1000000, globals={
          **ctx, 'fn': naive_make_A
      }))
print('ast level generated function costs',
      timeit('fn(data)', number=1000000, globals={
          **ctx, 'fn': ast_make_A
      }))
