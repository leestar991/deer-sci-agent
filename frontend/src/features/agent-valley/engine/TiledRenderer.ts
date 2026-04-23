import * as PIXI from 'pixi.js';

/**
 * Loads a Tiled JSON export, renders tile layers into a PIXI.Container.
 */
export default class TiledRenderer {
  data: any;
  options: any;
  tileW: number;
  tileH: number;
  mapW: number;
  mapH: number;
  pixelW: number;
  pixelH: number;
  tilesets: any[] = [];
  container: PIXI.Container;
  private _contentBounds: any = null;

  constructor(mapData: any, options: any = {}) {
    this.data = mapData;
    this.options = options;
    this.tileW = mapData.tilewidth;
    this.tileH = mapData.tileheight;
    this.mapW = mapData.width;
    this.mapH = mapData.height;
    this.pixelW = this.mapW * this.tileW;
    this.pixelH = this.mapH * this.tileH;
    this.container = new PIXI.Container();
    this.container.sortableChildren = true;
  }

  private _normalizeLayerName(name: string): string {
    return String(name || '').trim().toLowerCase();
  }

  private _getRequestedVisualLayerName(): string {
    return this._normalizeLayerName(this.options.visualLayerName);
  }

  private _getRequestedTilesetName(): string {
    return this._normalizeLayerName(this.options.tilesetName);
  }

  private _getRequestedImageAsset(): string {
    return String(this.options.imageAsset || '').trim();
  }

  private _shouldRenderWholeImage(): boolean {
    return this.options.renderMode === 'whole-image';
  }

  /**
   * Load all tileset images referenced by the map.
   */
  async loadTilesets(basePath: string, mapUrl: string): Promise<void> {
    const mapDir = mapUrl
      ? mapUrl.substring(0, mapUrl.lastIndexOf('/') + 1)
      : (basePath ? `${basePath}/` : '/');

    for (const tsEntry of this.data.tilesets) {
      let tsData = tsEntry;

      // External tileset
      if (tsEntry.source && !tsEntry.image) {
        const tsjUrl = mapDir + tsEntry.source;
        try {
          const res = await fetch(tsjUrl);
          const ext = await res.json();
          tsData = { ...ext, firstgid: tsEntry.firstgid };
          const tsjDir = tsjUrl.substring(0, tsjUrl.lastIndexOf('/') + 1);
          (tsData as any)._imgBase = tsjDir;
        } catch (e) {
          console.warn('TiledRenderer: failed to load external tileset', tsjUrl, e);
          continue;
        }
      }

      const imgBase = (tsData as any)._imgBase || mapDir;
      const imgPath = imgBase + tsData.image;

      try {
        const tex = await PIXI.Assets.load(imgPath);
        tex.baseTexture.scaleMode = PIXI.SCALE_MODES.NEAREST;
        const tw = tsData.tilewidth || this.tileW;
        const th = tsData.tileheight || this.tileH;
        const cols = tsData.columns || Math.floor(tsData.imagewidth / tw);
        this.tilesets.push({
          ...tsData,
          tilewidth: tw,
          tileheight: th,
          texture: tex,
          cols,
        });
      } catch (e) {
        console.warn('TiledRenderer: failed to load tileset image', imgPath, e);
      }
    }
    this.tilesets.sort((a, b) => b.firstgid - a.firstgid);
  }

  private _findWholeImageTileset(): any {
    const requestedTilesetName = this._getRequestedTilesetName();
    const requestedImageAsset = this._getRequestedImageAsset();

    return this.tilesets.find((tileset) => {
      const matchesName = requestedTilesetName
        ? this._normalizeLayerName(tileset.name) === requestedTilesetName
        : false;
      const matchesImage = requestedImageAsset
        ? requestedImageAsset.endsWith(`/${tileset.image}`) || requestedImageAsset === tileset.image
        : false;
      return matchesName || matchesImage;
    }) || null;
  }

  private _renderWholeImageLayer(): PIXI.Container | null {
    const tileset = this._findWholeImageTileset();
    if (!tileset?.texture) return null;

    const sprite = new PIXI.Sprite(tileset.texture);
    sprite.x = 0;
    sprite.y = 0;
    sprite.zIndex = 0;
    sprite.eventMode = 'none';
    this.container.addChild(sprite);

    return this.container;
  }

  /** Resolve a global tile ID to tileset info */
  private _resolve(gid: number): any {
    const FLIP_H = 0x80000000, FLIP_V = 0x40000000, FLIP_D = 0x20000000;
    const realGid = gid & ~(FLIP_H | FLIP_V | FLIP_D);
    for (const ts of this.tilesets) {
      if (realGid >= ts.firstgid) {
        const lid = realGid - ts.firstgid;
        return {
          ts,
          col: lid % ts.cols,
          row: Math.floor(lid / ts.cols),
          flipH: !!(gid & FLIP_H),
          flipV: !!(gid & FLIP_V),
          flipD: !!(gid & FLIP_D),
        };
      }
    }
    return null;
  }

  /** Render all visible tile layers */
  render(): PIXI.Container {
    if (this._shouldRenderWholeImage()) {
      const wholeImage = this._renderWholeImageLayer();
      if (wholeImage) return wholeImage;
    }

    // Simple rendering: just render all tile layers
    const layers = this.data.layers || [];
    let zIdx = 0;

    for (const layer of layers) {
      if (layer.type !== 'tilelayer') continue;
      if (layer.visible === false) continue;

      const lc = new PIXI.Container();
      lc.zIndex = zIdx++;

      for (let y = 0; y < layer.height; y++) {
        for (let x = 0; x < layer.width; x++) {
          const gid = layer.data[y * layer.width + x];
          if (gid === 0) continue;
          const r = this._resolve(gid);
          if (!r) continue;

          const rect = new PIXI.Rectangle(
            r.col * r.ts.tilewidth,
            r.row * r.ts.tileheight,
            r.ts.tilewidth,
            r.ts.tileheight
          );
          const tex = new PIXI.Texture(r.ts.texture.baseTexture, rect);
          const sprite = new PIXI.Sprite(tex);

          sprite.x = x * this.tileW;
          sprite.y = y * this.tileH;
          if (r.flipH) { sprite.scale.x = -1; sprite.x += this.tileW; }
          if (r.flipV) { sprite.scale.y = -1; sprite.y += this.tileH; }

          lc.addChild(sprite);
        }
      }
      this.container.addChild(lc);
    }
    return this.container;
  }

  getContentBounds(): any {
    if (this._contentBounds) return this._contentBounds;

    this._contentBounds = {
      top: 0,
      bottom: this.mapH - 1,
      left: 0,
      right: this.mapW - 1,
      pixelX: 0,
      pixelY: 0,
      pixelW: this.pixelW,
      pixelH: this.pixelH,
    };
    return this._contentBounds;
  }
}
