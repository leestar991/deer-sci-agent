import * as PIXI from 'pixi.js';

const FW = 32; // Frame width
const FH = 64; // Frame height

export interface CharFrames {
  front: PIXI.Texture[];
  back: PIXI.Texture[];
  left: PIXI.Texture[];
  right: PIXI.Texture[];
  idle: PIXI.Texture[];
  idleRight: PIXI.Texture[];
  idleBack: PIXI.Texture[];
  idleLeft: PIXI.Texture[];
  idleFront: PIXI.Texture[];
  phone: PIXI.Texture[];
  reading: PIXI.Texture[];
}

/**
 * Loads all character sprite sheets and builds frame maps.
 *
 * Sheet layouts:
 *   _idle_anim / _run: 24 frames of 32×64, grouped in 6:
 *     [0-5] right, [6-11] back, [12-17] left, [18-23] front
 *   _phone: 9 frames of 32×64 (front-facing)
 *   _reading: 18 frames of 32×64 (front-facing)
 */
export default class SpriteLoader {
  charFrames: Record<string, CharFrames> = {};

  /** Load all character sheets. onProgress(0-1) for UI feedback. */
  async load(charNames: string[], charBase: string, onProgress?: (progress: number) => void): Promise<void> {
    PIXI.BaseTexture.defaultOptions.scaleMode = PIXI.SCALE_MODES.NEAREST;

    const coreUrls: string[] = [];
    const optionalUrls: string[] = [];

    for (const name of charNames) {
      coreUrls.push(charBase + name + '_run_32x32.png');
      coreUrls.push(charBase + name + '_idle_anim_32x32.png');
      optionalUrls.push(charBase + name + '_phone_32x32.png');
      optionalUrls.push(charBase + name + '_reading_32x32.png');
    }

    await PIXI.Assets.load(coreUrls, (p) => onProgress?.(p * 0.8))
      .catch(() => console.warn('Some core assets failed to load'));

    // Optional (phone/reading) — don't block on failure
    await Promise.allSettled(optionalUrls.map(u => PIXI.Assets.load(u)));
    onProgress?.(1);

    this._buildFrames(charNames, charBase);
  }

  private _buildFrames(charNames: string[], charBase: string): void {
    for (const name of charNames) {
      const runUrl = charBase + name + '_run_32x32.png';
      const idleUrl = charBase + name + '_idle_anim_32x32.png';
      const phoneUrl = charBase + name + '_phone_32x32.png';
      const readingUrl = charBase + name + '_reading_32x32.png';

      try {
        const runBT = PIXI.BaseTexture.from(runUrl);
        const idleBT = PIXI.BaseTexture.from(idleUrl);
        runBT.scaleMode = PIXI.SCALE_MODES.NEAREST;
        idleBT.scaleMode = PIXI.SCALE_MODES.NEAREST;

        const cut = (bt: PIXI.BaseTexture, start: number, end: number): PIXI.Texture[] => {
          const arr: PIXI.Texture[] = [];
          for (let i = start; i < end; i++) {
            arr.push(new PIXI.Texture(bt, new PIXI.Rectangle(i * FW, 0, FW, FH)));
          }
          return arr;
        };

        // Running directions
        const right = cut(runBT, 0, 6);
        const back = cut(runBT, 6, 12);
        const left = cut(runBT, 12, 18);
        const front = cut(runBT, 18, 24);

        // Idle directions
        const idleRight = cut(idleBT, 0, 6);
        const idleBack = cut(idleBT, 6, 12);
        const idleLeft = cut(idleBT, 12, 18);
        const idleFront = cut(idleBT, 18, 24);
        const idle = [...idleFront];

        // Optional: phone (9 frames) & reading (18 frames)
        let phone: PIXI.Texture[] = [];
        try {
          const bt = PIXI.BaseTexture.from(phoneUrl);
          if (bt && bt.valid) {
            bt.scaleMode = PIXI.SCALE_MODES.NEAREST;
            phone = cut(bt, 0, 9);
          }
        } catch (_) {
          // Phone animation not available
        }

        let reading: PIXI.Texture[] = [];
        try {
          const bt = PIXI.BaseTexture.from(readingUrl);
          if (bt && bt.valid) {
            bt.scaleMode = PIXI.SCALE_MODES.NEAREST;
            reading = cut(bt, 0, 18);
          }
        } catch (_) {
          // Reading animation not available
        }

        this.charFrames[name] = {
          front,
          back,
          left,
          right,
          idle,
          idleRight,
          idleBack,
          idleLeft,
          idleFront,
          phone,
          reading,
        };
      } catch (e) {
        console.warn('SpriteLoader: failed to build frames for', name, e);
      }
    }
  }
}
