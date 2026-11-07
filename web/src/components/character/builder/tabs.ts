/** The Character Lab builder's tabs: which parts and paint pots each one shows. */

export type Section =
  | { type: 'body' }
  | { type: 'part'; category: string; title: string }
  | { type: 'extras'; title: string }
  | { type: 'paint'; slot: string; title: string }

export interface BuilderTab {
  id: string
  label: string
  sections: Section[]
}

export const TABS: BuilderTab[] = [
  {
    id: 'body',
    label: 'Body',
    sections: [
      { type: 'body' },
      { type: 'paint', slot: 'skin', title: 'Skin' },
      { type: 'paint', slot: 'card', title: 'Card colour' },
    ],
  },
  {
    id: 'face',
    label: 'Face',
    sections: [
      { type: 'part', category: 'face_shape', title: 'Face shape' },
      { type: 'part', category: 'nose', title: 'Nose' },
      { type: 'part', category: 'brows', title: 'Eyebrows' },
    ],
  },
  { id: 'eyes', label: 'Eyes', sections: [{ type: 'part', category: 'eyes', title: 'Eyes' }] },
  {
    id: 'hair',
    label: 'Hair',
    sections: [
      { type: 'part', category: 'hair', title: 'Hair' },
      { type: 'paint', slot: 'hair', title: 'Hair colour' },
    ],
  },
  {
    id: 'hats',
    label: 'Hats',
    sections: [
      { type: 'part', category: 'headwear', title: 'Hats' },
      { type: 'paint', slot: 'hat', title: 'Hat colour' },
    ],
  },
  {
    id: 'outfit',
    label: 'Outfit',
    sections: [
      { type: 'part', category: 'top', title: 'Tops' },
      { type: 'paint', slot: 'top', title: 'Top colour' },
      { type: 'part', category: 'bottom', title: 'Bottoms' },
      { type: 'paint', slot: 'bottom', title: 'Bottoms colour' },
      { type: 'part', category: 'shoes', title: 'Shoes' },
      { type: 'paint', slot: 'shoes', title: 'Shoes colour' },
    ],
  },
  {
    id: 'extras',
    label: 'Extras',
    sections: [
      { type: 'extras', title: 'Extras' },
      { type: 'paint', slot: 'cape', title: 'Cape colour' },
      { type: 'paint', slot: 'backpack', title: 'Backpack colour' },
    ],
  },
]

export type PreviewView = 'front' | 'three_quarter' | 'side' | 'back'

/** The pose that shows each view in the builder preview. */
export const VIEW_POSE: Record<PreviewView, string> = {
  front: 'front',
  three_quarter: 'three_quarter_right',
  side: 'side_right',
  back: 'back',
}

/** Parts shown as a close-up of the head; the rest show the whole character. */
export const HEAD_CATEGORIES = new Set(['face_shape', 'nose', 'brows', 'eyes', 'hair', 'headwear'])
/** Extras drawn behind the body show best from a ¾ view. */
export const THREE_QUARTER_EXTRAS = new Set(['cape', 'backpack'])
