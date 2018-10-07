# https://github.com/graphql-python/graphene/blob/master/examples/starwars_relay/data.py

import typing as t
from pprint import pprint
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
ast_generate()

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
