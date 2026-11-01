# assist-api

```sh
pip install assist-api
```
## Quick Start
```python
from assist_api import AssistAPI

with AssistAPI() as api:
  major = api.query_major('San Joaquin Delta College', 'University of California, Berkeley', 2026, 'Computer Science, B.A.')
  agreement = api.get_agreement(my_major)
  print(agreement)
```

This is a simple example package. You can use
[GitHub-flavored Markdown](https://guides.github.com/features/mastering-markdown/)
to write your content.
