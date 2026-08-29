import 'package:behavior_pattern_kit/behavior_pattern_kit.dart';
import 'package:test/test.dart';

void main() {
  group('BehaviorProfile', () {
    test('defaults are empty/zero', () {
      const p = BehaviorProfile();
      expect(p.metrics, isEmpty);
      expect(p.sampleCount, 0);
      expect(p.totalEvents, 0);
      expect(p.recentEvents, isEmpty);
    });

    test('copyWith overrides only given fields', () {
      const p = BehaviorProfile(metrics: {'a': 1.0}, sampleCount: 5);
      final p2 = p.copyWith(sampleCount: 6);
      expect(p2.metrics, {'a': 1.0}); // untouched
      expect(p2.sampleCount, 6);
    });

    test('toJson/fromJson round-trips', () {
      const p = BehaviorProfile(
        metrics: {'aggressionRate': 0.42, 'bluffRate': 0.1},
        sampleCount: 12,
        totalEvents: 40,
        recentEvents: [
          {'action': 'raise', 'amount': 50},
          {'action': 'fold'},
        ],
      );
      final restored = BehaviorProfile.fromJson(p.toJson());
      expect(restored.metrics, p.metrics);
      expect(restored.sampleCount, 12);
      expect(restored.totalEvents, 40);
      expect(restored.recentEvents, p.recentEvents);
    });

    test('fromJson tolerates missing/null fields', () {
      final p = BehaviorProfile.fromJson({});
      expect(p.metrics, isEmpty);
      expect(p.sampleCount, 0);
      expect(p.recentEvents, isEmpty);
    });

    test('fromJson coerces int metric values to double', () {
      final p = BehaviorProfile.fromJson({
        'metrics': {'winRate': 1}, // int, not double -- as JSON decoding commonly produces
      });
      expect(p.metrics['winRate'], 1.0);
      expect(p.metrics['winRate'], isA<double>());
    });
  });

  group('PairwiseBehaviorStore', () {
    late PairwiseBehaviorStore store;
    setUp(() => store = PairwiseBehaviorStore());

    test('get on unknown pair returns null', () {
      expect(store.get('a', 'b'), isNull);
    });

    test('set then get round-trips', () {
      const profile = BehaviorProfile(metrics: {'x': 1.0});
      store.set('player1', 'ai_hard', profile);
      expect(store.get('player1', 'ai_hard'), profile);
    });

    test('direction matters -- a-vs-b is independent of b-vs-a', () {
      store.set('a', 'b', const BehaviorProfile(metrics: {'x': 1.0}));
      store.set('b', 'a', const BehaviorProfile(metrics: {'x': 2.0}));
      expect(store.get('a', 'b')!.metrics['x'], 1.0);
      expect(store.get('b', 'a')!.metrics['x'], 2.0);
    });

    test('has() reflects presence', () {
      expect(store.has('a', 'b'), isFalse);
      store.set('a', 'b', const BehaviorProfile());
      expect(store.has('a', 'b'), isTrue);
    });

    test('pairs() lists every stored relationship', () {
      store.set('p1', 'ai_a', const BehaviorProfile());
      store.set('p1', 'ai_b', const BehaviorProfile());
      expect(store.pairs().toSet(), {('p1', 'ai_a'), ('p1', 'ai_b')});
    });

    test('ids containing the literal "_vs_" substring do not collide in-memory', () {
      // regression: the old string-concatenated key made these two
      // distinct pairs indistinguishable ('a_vs_b'+'c' and 'a'+'b_vs_c'
      // both produced the storage key 'a_vs_b_vs_c'). The record-keyed
      // store treats them as what they are: two different pairs.
      store.set('a_vs_b', 'c', const BehaviorProfile(metrics: {'x': 1.0}));
      store.set('a', 'b_vs_c', const BehaviorProfile(metrics: {'x': 2.0}));

      expect(store.get('a_vs_b', 'c')!.metrics['x'], 1.0);
      expect(store.get('a', 'b_vs_c')!.metrics['x'], 2.0);
      expect(store.pairs().toSet(), {('a_vs_b', 'c'), ('a', 'b_vs_c')});
    });

    test('toMap/fromMap round-trips the whole store', () {
      store.set('a', 'b', const BehaviorProfile(metrics: {'x': 1.0}, sampleCount: 3));
      final dumped = store.toMap();

      final restored = PairwiseBehaviorStore();
      restored.fromMap(dumped);
      expect(restored.get('a', 'b')!.metrics, {'x': 1.0});
      expect(restored.get('a', 'b')!.sampleCount, 3);
    });

    test('toMap/fromMap boundary still can\'t disambiguate "_vs_" in ids (documented, not fixed)', () {
      // Unlike the in-memory ops above, the JSON-string-keyed wire format
      // (toMap/fromMap) still joins pairs as "fromId_vs_toId" -- that's
      // the same caveat the source app always had at its persistence
      // boundary, now confined to exactly these two methods rather than
      // leaking into every store operation. Not something this kit fixes,
      // documented so a buyer doesn't assume persistence is collision-free
      // too.
      store.set('a_vs_b', 'c', const BehaviorProfile(metrics: {'x': 1.0}));
      final restored = PairwiseBehaviorStore()..fromMap(store.toMap());
      expect(restored.get('a_vs_b', 'c'), isNull); // round-trip does not preserve this pair
      expect(restored.get('a', 'b_vs_c'), isNotNull); // it lands on the wrong pair instead
    });

    test('fromMap ignores malformed entries instead of throwing', () {
      expect(
        () => store.fromMap({'a_vs_b': 'not a map'}),
        returnsNormally,
      );
      expect(store.get('a', 'b'), isNull);
    });

    test('clear empties the store', () {
      store.set('a', 'b', const BehaviorProfile());
      store.clear();
      expect(store.get('a', 'b'), isNull);
    });
  });
}
