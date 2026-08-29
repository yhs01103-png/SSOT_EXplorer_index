/// Generalized from poker_app's `PatternStore`/`PatternData` -- that
/// version was hardcoded to five poker-specific fields
/// (preflopRaiseRate, foldToRaiseRate, bluffRate, aggressionTrend,
/// avgPotSize) on a pairwise `"${fromId}_vs_$toId"` key. The pairwise
/// key-and-store shape is the reusable part; the metrics themselves
/// aren't -- so here they're a caller-defined `Map<String, double>`
/// instead of fixed fields.
///
/// This is a pure data store, deliberately: it does not compute metrics
/// from raw events for you. The source app's actual rate-computation
/// logic (how a stream of hands becomes a `bluffRate`) lives in game
/// logic this package never saw and has no business generalizing --
/// only the "keep a profile of what actor A has observed about actor
/// B, keyed by the pair, serializable, mergeable" shape was proven
/// reusable. Bring your own metric computation; this just holds the
/// result of it.
library;

class BehaviorProfile {
  /// Caller-defined named metrics (e.g. `{'aggressionRate': 0.4,
  /// 'bluffRate': 0.12}`) -- this package assigns no meaning to any key.
  final Map<String, double> metrics;

  /// How many observations these [metrics] were computed from -- separate
  /// from [totalEvents] so a caller can implement a rolling window
  /// (metrics computed from the last N events) while still tracking the
  /// lifetime total.
  final int sampleCount;

  final int totalEvents;

  /// Raw recent events, caller-shaped (each one whatever your domain's
  /// event record serializes to). Not interpreted here -- kept only so
  /// a UI can show "recent hands" (or whatever your events are) without
  /// a separate store.
  final List<Map<String, dynamic>> recentEvents;

  const BehaviorProfile({
    this.metrics = const {},
    this.sampleCount = 0,
    this.totalEvents = 0,
    this.recentEvents = const [],
  });

  BehaviorProfile copyWith({
    Map<String, double>? metrics,
    int? sampleCount,
    int? totalEvents,
    List<Map<String, dynamic>>? recentEvents,
  }) =>
      BehaviorProfile(
        metrics: metrics ?? this.metrics,
        sampleCount: sampleCount ?? this.sampleCount,
        totalEvents: totalEvents ?? this.totalEvents,
        recentEvents: recentEvents ?? this.recentEvents,
      );

  Map<String, dynamic> toJson() => {
        'metrics': metrics,
        'sampleCount': sampleCount,
        'totalEvents': totalEvents,
        'recentEvents': recentEvents,
      };

  factory BehaviorProfile.fromJson(Map<String, dynamic> json) {
    final rawMetrics = json['metrics'];
    final metrics = rawMetrics is Map
        ? rawMetrics.map((k, v) => MapEntry(k as String, (v as num).toDouble()))
        : <String, double>{};

    final rawEvents = json['recentEvents'];
    final events = rawEvents is List
        ? rawEvents.whereType<Map>().map((e) => e.cast<String, dynamic>()).toList()
        : <Map<String, dynamic>>[];

    return BehaviorProfile(
      metrics: metrics,
      sampleCount: (json['sampleCount'] as num?)?.toInt() ?? 0,
      totalEvents: (json['totalEvents'] as num?)?.toInt() ?? 0,
      recentEvents: events,
    );
  }
}

/// Pairwise store: "what does `fromId` know/believe about `toId`".
/// In-memory by default (matches the source, which held everything in a
/// static `Map` for the lifetime of a game session) -- call [toMap]/
/// [fromMap] around your own persistence if a profile needs to survive
/// restarts, same division of responsibility as the source app.
class PairwiseBehaviorStore {
  /// Keyed by the pair directly as a record, not a joined string -- every
  /// in-memory operation (`get`/`set`/`has`/`pairs`) is therefore exact,
  /// with no string-splitting involved and no ambiguity if an id happens
  /// to contain "_vs_". [pairs] used to reconstruct `(fromId, toId)` by
  /// splitting the storage key back apart; now it just returns the key
  /// type the store already uses internally.
  final Map<(String, String), BehaviorProfile> _store = {};

  BehaviorProfile? get(String fromId, String toId) => _store[(fromId, toId)];

  void set(String fromId, String toId, BehaviorProfile profile) {
    _store[(fromId, toId)] = profile;
  }

  bool has(String fromId, String toId) => _store.containsKey((fromId, toId));

  /// All pairs currently held, as `(fromId, toId)` -- the store's own key
  /// type, returned as-is.
  List<(String, String)> pairs() => _store.keys.toList();

  /// Serializes to a JSON-safe `Map<String, dynamic>`. JSON object keys
  /// must be strings, so pairs are joined as `"fromId_vs_toId"` only at
  /// this boundary -- the in-memory store itself never builds or parses
  /// that string. If an id contains the literal substring `"_vs_"`,
  /// [fromMap] can't unambiguously recover the original split; that
  /// caveat is now confined to exactly these two methods instead of
  /// leaking into every store operation the way it used to.
  Map<String, dynamic> toMap() =>
      _store.map((k, v) => MapEntry('${k.$1}_vs_${k.$2}', v.toJson()));

  void fromMap(Map<String, dynamic> map) {
    for (final entry in map.entries) {
      if (entry.value is Map) {
        final parts = entry.key.split('_vs_');
        final key = (parts.first, parts.sublist(1).join('_vs_'));
        _store[key] = BehaviorProfile.fromJson((entry.value as Map).cast<String, dynamic>());
      }
    }
  }

  void clear() => _store.clear();
}
