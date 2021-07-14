/// <reference types="jest" />
import Vue from 'vue';
import CompositionApi from '@vue/composition-api';
import Track, { ConfidencePair, TrackData } from './track';
import { RectBounds } from './utils';

Vue.use(CompositionApi);

describe('Track', () => {
  it('should create new instances from JSON', () => {
    const itrack: TrackData = {
      attributes: {},
      begin: 0,
      end: 100,
      confidencePairs: [
        ['foo', 1],
        ['bar', 0.9],
      ],
      features: [
        {
          frame: 0,
          bounds: [1, 2, 3, 4],
          head: [1, 2],
        },
      ],
      meta: {},
      trackId: 1,
    };
    const t = Track.fromJSON(itrack);
    expect(t).toBeInstanceOf(Track);
    expect(t.begin).toBe(0);
    expect(t.end).toBe(100);
    expect(t.confidencePairs).toHaveLength(2);
  });

  it('should correct its begin and end based on setFeature', () => {
    const track = new Track(0, {
      meta: {},
      begin: 0,
      end: 0,
    });
    const feature = {
      frame: 1,
      bounds: [1, 2, 3, 4] as RectBounds,
      keyframe: true,
    };
    track.setFeature(feature);
    const f0 = track.getFeature(0);
    const f1 = track.getFeature(1);
    expect(f0).toStrictEqual([null, feature, null]);
    expect(f1).toStrictEqual([feature, feature, feature]);
    expect(track.begin).toBe(1);
    expect(track.end).toBe(1);
  });

  it('should correctly reset begin and end on firstFeature', () => {
    const track = new Track(0, {
      meta: {},
      begin: 8,
      end: 8,
    });
    const feature = {
      frame: 3,
      bounds: [1, 2, 3, 4] as RectBounds,
      keyframe: true,
    };
    track.setFeature(feature);
    const f2 = track.getFeature(2);
    const f3 = track.getFeature(3);
    const f4 = track.getFeature(4);
    expect(f2).toStrictEqual([null, feature, null]);
    expect(f3).toStrictEqual([feature, feature, feature]);
    expect(f4).toStrictEqual([null, null, feature]);
    expect(track.begin).toBe(3);
    expect(track.end).toBe(3);
    expect(() => track.setFeature({
      frame: 4,
    })).toThrow('must be called with keyframe');
  });

  it('should fail to initialize with non-sparse array', () => {
    const features = [
      { frame: 1, bounds: [1, 2, 3, 4] as RectBounds, keyframe: true },
    ];
    expect(() => new Track(1, {
      meta: {},
      begin: 1,
      end: 1,
      features,
      confidencePairs: [['foo', 1]],
    })).toThrowError();
  });

  it('Indexing Types', () => {
    const itrack: TrackData = {
      attributes: {},
      begin: 0,
      end: 100,
      confidencePairs: [
        ['foo', 1],
        ['bar', 0.9],
      ],
      features: [
        {
          frame: 0,
          bounds: [1, 2, 3, 4],
          head: [1, 2],
        },
      ],
      meta: {},
      trackId: 1,
    };
    const t = Track.fromJSON(itrack);
    expect(t.getType()).toEqual(['foo', 1]);
    expect(t.getType(1)).toEqual(['bar', 0.9]);
    expect(t.getType(0)).toEqual(['foo', 1.0]);
    expect(() => t.getType(-1)).toThrow('Index Error: The requested confidencePairs index does not exist.');
    t.setType('newType');
    expect(t.getType()).toEqual(['newType', 1]);
    // Testing type out of range
    expect(() => t.getType(1)).toThrow('Index Error: The requested confidencePairs index does not exist.');
    t.setType('lowType', 0.25);
    expect(t.getType()).toEqual(['newType', 1]);
    expect(() => t.getType(20)).toThrow('Index Error: The requested confidencePairs index does not exist.');
    const track2 = new Track(0, {
      meta: {},
      begin: 0,
      end: 0,
      confidencePairs: [
        ['foo', 0.1],
      ],
    });
    track2.setType('foo', 0.2);
    track2.setType('bar', 0.4);
    expect(track2.confidencePairs).toEqual([['bar', 0.4], ['foo', 0.2]]);
    track2.setType('foo', 0.1);
    expect(track2.confidencePairs).toEqual([['bar', 0.4], ['foo', 0.1]]);
    track2.setType('baz', 1);
    expect(track2.confidencePairs).toEqual([['baz', 1]]);
  });

  it('merges tracks', () => {
    const track0tmpl: TrackData = {
      begin: 0,
      end: 10,
      attributes: {
        a: 'a',
      },
      confidencePairs: [
        ['a', 0.1],
        ['b', 0.2],
      ],
      features: [
        {
          frame: 0,
          bounds: [0, 0, 0, 0],
          attributes: { a1: 'a1' },
        },
        {
          frame: 10,
          bounds: [10, 10, 10, 10],
        },
      ],
      meta: {},
      trackId: 0,
    };
    const track1tmpl: TrackData = {
      begin: 2,
      end: 12,
      attributes: {
        a: 'b',
      },
      confidencePairs: [
        ['a', 0.2],
        ['c', 0.3],
      ],
      features: [
        {
          frame: 2,
          bounds: [2, 2, 2, 2],
          interpolate: true,
          attributes: { a1: 'b1' },
        },
        {
          frame: 10,
          interpolate: true,
          bounds: [11, 11, 11, 11],
          attributes: { a1: 'b1' },
        },
      ],
      meta: {},
      trackId: 0,
    };
    const track0 = Track.fromJSON(track0tmpl);
    track0.merge([Track.fromJSON(track1tmpl)]);
    expect(track0.attributes).toEqual({ a: 'a' });
    expect(track0.begin).toBe(0);
    expect(track0.end).toBe(10);
    expect(track0.getFeature(0)[0]?.bounds).toEqual([0, 0, 0, 0]);
    expect(track0.getFeature(10)[0]?.bounds).toEqual([10, 10, 10, 10]);
    expect(track0.getFeature(10)[0]?.attributes).toBeUndefined();
    expect(track0.getFeature(10)[0]?.interpolate).toBeFalsy();
    expect(track0.trackId).toBe(0);
    expect(track0.featureIndex.length).toBe(3);
    expect(track0.confidencePairs).toEqual([['c', 0.3], ['a', 0.2], ['b', 0.2]]);
  });
  it('toggleInterpolation(frame) and toggleKeyframe(frame)', () => {
    const itrack: TrackData = {
      attributes: {},
      begin: 6,
      end: 12,
      confidencePairs: [
        ['foo', 1],
        ['bar', 0.9],
      ],
      features: [
        {
          frame: 6,
          bounds: [0, 0, 0, 0],
        },
        {
          frame: 12,
          bounds: [100, 100, 100, 100],
        },
      ],
      meta: {},
      trackId: 1,
    };
    const t = Track.fromJSON(itrack);
    t.toggleInterpolation(9);
    expect(t.getFeature(9)[0]?.bounds).toEqual([50, 50, 50, 50]);
    // Add in feature beyond interpolation range and test
    const feature = {
      frame: 18,
      bounds: [300, 300, 300, 300] as RectBounds,
      keyframe: true,
    };
    t.setFeature(feature);
    expect(t.getFeature(15)[0]).toEqual(null);
    expect(t.getFeature(15)[1]?.bounds).toEqual([100, 100, 100, 100]);
    expect(t.getFeature(15)[2]?.bounds).toEqual([300, 300, 300, 300]);
    // Turn interpolation on for new range
    t.toggleInterpolation(12); // Turn interpolation on
    expect(t.getFeature(15)[0]?.bounds).toEqual([200, 200, 200, 200]);
    t.toggleInterpolation(6); // Turn interpolation for lower range off
    expect(t.getFeature(7)[0]).toEqual(null);
    expect(t.getFeature(7)[1]?.bounds).toEqual([0, 0, 0, 0]);
    expect(t.getFeature(7)[2]?.bounds).toEqual([100, 100, 100, 100]);
    t.toggleInterpolation(6); // Turn interpolation back on
    // toggleKeyframe() testing
    t.toggleKeyframe(12); // remove keyframe at 12, 6=0,0,0,0 and 18=300,300,300,300
    expect(t.getFeature(12)[0]?.bounds).toEqual([150, 150, 150, 150]);
    expect(t.getFeature(12)[0]?.keyframe).toEqual(false);
    t.toggleKeyframe(12); // locks interpolated frame as a new keyframe
    expect(t.getFeature(12)[0]?.bounds).toEqual([150, 150, 150, 150]);
    expect(t.getFeature(12)[0]?.keyframe).toEqual(true);
    // toggle keyframe at beginning/end and track length adjusts
    t.toggleKeyframe(6);
    expect(t.begin).toEqual(12);
    // toggleKeyframe outside current track temporal bounds
    t.toggleKeyframe(6);
    expect(t.begin).toEqual(6);
    expect(t.getFeature(12)[0]?.bounds).toEqual([150, 150, 150, 150]);
    expect(t.getFeature(12)[0]?.keyframe).toEqual(true);
    // toggleKeyframe on a single feature expect error
    t.deleteFeature(18);
    t.deleteFeature(12);
    expect(t.begin).toEqual(t.end);
    expect(() => t.toggleKeyframe(t.begin)).toThrow('This is the only keyframe in Track:1 it cannot be removed');
    // Turn off interpolation
    t.toggleKeyframe(12);
    expect(t.getFeature(12)[0]?.keyframe).toEqual(true);
    expect(t.getFeature(8)[1]?.frame).toEqual(6);
    expect(t.getFeature(8)[2]?.frame).toEqual(12);
    // Remove lower keyframe
    t.toggleKeyframe(6);
    // Now try to remove remaining keyframe
    expect(t.begin).toEqual(t.end);
    expect(() => t.toggleKeyframe(12)).toThrow('This is the only keyframe in Track:1 it cannot be removed');
  });
});

describe('trackExceedsThreshold', () => {
  it('correctly determine if a confidence pair set exceeds any thresholds', () => {
    const pairs: ConfidencePair[] = [
      ['foo', 0.05],
      ['bar', 0.1],
      ['baz', 0.1000001],
    ];
    expect(Track.trackExceedsThreshold(pairs, {
      default: 0.1,
    })).toEqual([
      ['bar', 0.1],
      ['baz', 0.1000001],
    ]);
    expect(Track.trackExceedsThreshold(pairs, {
      default: 2,
    })).toEqual([]);
    expect(Track.trackExceedsThreshold(pairs, {
      default: 0.1,
      baz: 0.2,
    })).toEqual([
      ['bar', 0.1],
    ]);
    expect(Track.trackExceedsThreshold(pairs, {
      bar: 0.2,
    })).toEqual([
      ['foo', 0.05],
      ['baz', 0.1000001],
    ]);
  });
  it('other edge cases', () => {
    expect(Track.trackExceedsThreshold([], {})).toEqual([]);
    expect(Track.trackExceedsThreshold([['foo', 1]], {})).toEqual([['foo', 1]]);
    expect(Track.trackExceedsThreshold([['foo', 0]], {})).toEqual([['foo', 0]]);
  });
});
