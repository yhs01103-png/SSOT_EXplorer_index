# Behavior Pattern Kit

A pairwise behavior-profile store: "what has actor A observed about
actor B's behavior." Generalized from a poker game's `PatternStore`,
which tracked things like an opponent's raise rate and bluff frequency
so the AI could adapt to a specific player over repeated hands.

## What this is

- **`BehaviorProfile`** — a caller-defined `Map<String, double>` of
  named metrics (nothing here assigns meaning to any key -- your domain
  decides what `"aggressionRate"` or `"bluffRate"` or `"trustScore"`
  means), plus a sample count, a lifetime event count, and a raw recent-
  events list for UI display.
- **`PairwiseBehaviorStore`** — keeps one `BehaviorProfile` per ordered
  `(fromId, toId)` pair, in memory (keyed internally by the `(String,
  String)` record itself, not a joined string -- `get`/`set`/`has`/`pairs`
  are exact even if an id contains unusual characters), with JSON-shaped
  `toMap()`/`fromMap()` for your own persistence.

## What this is *not*

This is a **store**, not a computation engine. It does not turn a
stream of game events into a `bluffRate` for you -- that logic is
irreducibly domain-specific (how you define "aggressive," what counts
as an "event," what window you average over) and lived in the source
app's game engine, not in the part that turned out to generalize. Bring
your own metric computation; this package holds the result of it and
gets it back to you keyed by who-observed-whom.

Use cases beyond the source's poker AI: an NPC that remembers how a
player typically negotiates, a tutoring app tracking which hint types
worked for which student, any multi-agent simulation where "agent A's
model of agent B" needs to survive across sessions.

## Install

Pure Dart, no Flutter dependency.

## Quick start

```dart
import 'package:behavior_pattern_kit/behavior_pattern_kit.dart';

final store = PairwiseBehaviorStore();

// After a hand/round/turn, your own game logic computes the metrics:
final updated = (store.get('ai_hard', 'player1') ?? const BehaviorProfile()).copyWith(
  metrics: {'aggressionRate': 0.42, 'bluffRate': 0.15},
  sampleCount: 12,
  totalEvents: 40,
);
store.set('ai_hard', 'player1', updated);

// Later, read it back to inform a decision:
final profile = store.get('ai_hard', 'player1');
if ((profile?.metrics['bluffRate'] ?? 0) > 0.3) {
  // this opponent bluffs often -- adjust strategy
}

// Persist across sessions with your own storage:
final json = store.toMap();
// ... write `json` somewhere ...
final restored = PairwiseBehaviorStore()..fromMap(json);
```

## What's *not* included

No license-key or activation logic. No persistence layer -- `toMap()`/
`fromMap()` hand you plain JSON-shaped data; writing it to disk/a
database is your call. No metric computation (see above).

`toMap()`/`fromMap()` join a pair as the JSON string key
`"fromId_vs_toId"` (JSON object keys must be strings) -- if an id
contains the literal substring `"_vs_"`, `fromMap()` can't unambiguously
recover the original split. In-memory operations (`get`/`set`/`has`/
`pairs`) don't have this limitation; only the serialize/deserialize
boundary does.

## Tests

```bash
dart pub get
dart test
```
