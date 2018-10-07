# generated-graphql
Show python meta-programming  with graphql.
(P.S: `collect` method for collecting nested data is not implemented yet.)

```python
import typing as t
from auto_json.schema_analyse import AutoJson, SchemaMonitor
from auto_json.graphql_naive import generate as naive_generate
from auto_json.graphql_ast import generate as ast_generate

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
```

Where the given data is:

```json
{
  "name": "school",
  "floors": [
    {
      "name": "sf1",
      "rooms": []
    },
    {
      "name": "sf2",
      "rooms": []
    },
    {
      "name": "sf3",
      "rooms": [
        {
          "name": "a304",
          "bookmark": {
            "link": "target"
          },
          "dimension_gate": {
            "name": "301",
            "floors": [
              {
                "name": "f1",
                "rooms": [
                  {
                    "bookmark": {},
                    "dimension_gate": null,
                    "name": "r1"
                  },
                  {
                    "bookmark": {},
                    "dimension_gate": null,
                    "name": "r2"
                  }
                ]
              },
              {
                "name": "f2",
                "rooms": [
                  {
                    "bookmark": {},
                    "dimension_gate": null,
                    "name": "r3"
                  },
                  {
                    "bookmark": {},
                    "dimension_gate": null,
                    "name": "r4"
                  }
                ]
              }
            ]
          }
        }
      ]
    }
  ]
}

```