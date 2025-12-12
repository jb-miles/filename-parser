# Stash GraphQL API Quick Reference
## Studio Queries Cheat Sheet

---

## 🚀 Quick Start

### Connection Setup

```python
from stash_interface import StashInterface

# Initialize from plugin input
stash = StashInterface(input_data['server_connection'])
```

---

## 📋 Common Operations

### Find Studio by Name (Exact)

```python
studio = stash.find_studio_by_name("Brazzers", exact=True)
# Returns: {'id': '42', 'name': 'Brazzers', 'aliases': [], ...}
```

**GraphQL:**
```graphql
query {
  findStudios(
    studio_filter: { name: { value: "Brazzers", modifier: EQUALS } }
    filter: { per_page: 1 }
  ) {
    studios { id name aliases }
  }
}
```

---

### Find Studio by Name (Fuzzy)

```python
studio = stash.find_studio_by_name("brazz", exact=False)
# Returns: {'id': '42', 'name': 'Brazzers', ...}
```

**GraphQL:**
```graphql
query {
  findStudios(
    studio_filter: { name: { value: "brazz", modifier: INCLUDES } }
  ) {
    studios { id name }
  }
}
```

---

### Find Studio by Alias

```python
studio = stash.find_studio_by_alias("BBC")
# Returns: {'id': '15', 'name': 'Big Budget Cinema', 'aliases': ['BBC'], ...}
```

**GraphQL:**
```graphql
query {
  findStudios(
    studio_filter: { aliases: { value: "BBC", modifier: EQUALS } }
  ) {
    studios { id name aliases }
  }
}
```

---

### Match Token (Smart Matching)

```python
studio = stash.match_studio("Brazzers")
# Tries: exact name → alias → fuzzy name
```

---

### Get All Studios

```python
all_studios = stash.get_all_studios(page_size=100)
# Returns: List of all studios with pagination
```

---

## 🎯 Token Matching Pattern

```python
from tokenizer import Tokenizer

# 1. Tokenize filename
tokenizer = Tokenizer()
result = tokenizer.tokenize("[Brazzers] Scene Title (2024).mp4")

# 2. Match each token
for token in result.tokens:
    studio = stash.match_studio(token.value)
    if studio:
        print(f"Matched: {token.value} → {studio['name']}")
        break
```

---

## 📊 Filter Modifiers

| Modifier | Description | Example |
|----------|-------------|---------|
| `EQUALS` | Exact match | `"Brazzers"` matches only `"Brazzers"` |
| `NOT_EQUALS` | Not equal | Excludes exact match |
| `INCLUDES` | Contains substring | `"brazz"` matches `"Brazzers"` |
| `EXCLUDES` | Does not contain | Excludes substring |
| `MATCHES_REGEX` | Regex pattern | `"Bra.*"` matches `"Brazzers"` |
| `IS_NULL` | Value is NULL | Field is empty |
| `NOT_NULL` | Value is not NULL | Field has value |

---

## 🔍 Advanced Filters

### Filter by Scene Count

```graphql
query {
  findStudios(
    studio_filter: {
      scene_count: { value: 10, modifier: GREATER_THAN }
    }
  ) {
    studios { name scene_count }
  }
}
```

### Filter by Rating

```graphql
query {
  findStudios(
    studio_filter: {
      rating: { value: 80, modifier: GREATER_THAN }
    }
  ) {
    studios { name rating }
  }
}
```

### Filter Favorites Only

```graphql
query {
  findStudios(
    studio_filter: { is_favorite: true }
  ) {
    studios { name favorite }
  }
}
```

---

## 📦 Studio Object Structure

```json
{
  "id": "7",
  "name": "Bait Bus",
  "url": "https://baitbus.com/",
  "parent_id": null,
  "aliases": ["BB", "BaitBus"],
  "details": "Studio description...",
  "rating": 85,
  "favorite": true,
  "ignore_auto_tag": false,
  "created_at": "2025-09-03T15:00:22-05:00",
  "updated_at": "2025-09-13T08:13:33-05:00",
  "parent_studio": null,
  "child_studios": [],
  "scene_count": 150,
  "image_count": 50,
  "gallery_count": 20
}
```

---

## ⚡ Performance Tips

### ✅ DO

```python
# Cache for batch operations
matcher = CachedStudioMatcher(stash)
matcher.load_cache()  # Load once
results = matcher.match_tokens(many_tokens)  # Fast lookups

# Use exact matching first
studio = stash.find_studio_by_name(name, exact=True)
if not studio:
    studio = stash.find_studio_by_name(name, exact=False)

# Paginate large queries
studios = stash.get_all_studios(page_size=100)
```

### ❌ DON'T

```python
# Don't use deprecated queries
allStudios { ... }  # Use findStudios instead

# Don't hammer the API
for token in 1000_tokens:
    stash.match_studio(token)  # Use caching!

# Don't use fuzzy matching first
studio = stash.find_studio_by_name(name, exact=False)  # Too broad
```

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| `401 Unauthorized` | Check session cookie is being passed |
| Empty results | Try fuzzy matching or check database |
| Timeout | Reduce page size, add timeout parameter |
| Syntax error | Validate query in Playground first |

---

## 📚 Query Templates

### Template 1: Find with Fallback

```python
def find_studio_with_fallback(stash, token):
    """Try multiple strategies to find studio."""
    # 1. Exact name
    studio = stash.find_studio_by_name(token, exact=True)
    if studio: return studio

    # 2. Alias
    studio = stash.find_studio_by_alias(token)
    if studio: return studio

    # 3. Fuzzy name
    studio = stash.find_studio_by_name(token, exact=False)
    if studio: return studio

    return None
```

### Template 2: Batch Match with Cache

```python
def batch_match_studios(stash, tokens):
    """Match many tokens efficiently."""
    # Load all studios once
    all_studios = stash.get_all_studios()

    # Build lookup dict
    lookup = {}
    for studio in all_studios:
        lookup[studio['name'].lower()] = studio
        for alias in studio.get('aliases', []):
            lookup[alias.lower()] = studio

    # Match tokens
    return {
        token: lookup.get(token.lower())
        for token in tokens
    }
```

---

## 🔗 Endpoints

- **GraphQL API:** `http://localhost:9999/graphql`
- **Playground:** `http://localhost:9999/playground`
- **Schema:** `http://localhost:9999/graphql?query={__schema{types{name}}}`

---

## 📖 Full Documentation

See [STASH_API_DOCUMENTATION.md](./STASH_API_DOCUMENTATION.md) for complete reference.

---

**Version:** 1.0 | **Updated:** 2025-12-09