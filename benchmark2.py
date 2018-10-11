# https://github.com/graphql-python/graphene/blob/master/examples/starwars_relay/data.py

import typing as t
import copy
from pprint import pprint
from timeit import timeit
import json
from auto_json.schema_analyse import AutoJson, SchemaMonitor
from auto_json.graphql_naive import generate as naive_generate
from auto_json.graphql_ast import generate as ast_generate
with open('data.json', 'rb') as fr:
    data = json.load(fr)


class Building(AutoJson):
    name: str
    floors: t.List['Floor']


class Floor(AutoJson):
    name: str
    rooms: t.List['Room']


class Room(AutoJson):
    name: str
    dimension_gate: t.Optional[Building]
    bookmark: t.Dict[str, str]


SchemaMonitor.resolve(strict=True)

naive_generate()
f1 = Building.from_dict
ast_generate()
f2 = Building.from_dict
ast_generate(use_cython=True)
f3 = Building.from_dict

building = Building.from_dict(data)

assert building.name == 'school'

assert building.floors[0].name == 'sf1'

rooms = building.floors[2].rooms
a304 = rooms[0]

assert a304.name == 'a304'
assert 'link' in a304.bookmark
h301 = a304.dimension_gate
assert h301.name == '301'
assert len(h301.floors) == 2

inc = building


def expand_vertically(b: Building):
    b = Building.from_dict(b.to_dict())
    last = b.floors[-1].rooms[-1]

    while last.dimension_gate:
        last = last.dimension_gate.floors[-1].rooms[-1]

    last.dimension_gate = inc
    return b


def expand_horizontally(b: Building):
    b = Building.from_dict(b.to_dict())

    b.floors.append(
        Floor(
            name="_", rooms=[Room(name="_", bookmark={}, dimension_gate=inc)]))

    return b


def benchmark():
    print('==================')
    print('naive version costs: ',
          timeit('fn(data)', number=100000, globals={
              **ctx, 'fn': f1
          }))
    print('ast level generated function costs',
          timeit('fn(data)', number=100000, globals={
              **ctx, 'fn': f2
          }))

    print('ast level generated function with cython compilation costs',
          timeit('fn(data)', number=100000, globals={
              **ctx, 'fn': f3
          }))


building_ = building
for each in range(10):
    building_ = expand_vertically(building_)
    ctx = {'data': building_.to_dict()}
    benchmark()
