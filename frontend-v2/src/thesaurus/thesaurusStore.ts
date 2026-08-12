import { create } from 'zustand'

export type TagKind = 'synonyms' | 'related'

export interface ThesaurusEntry {
  id: string
  word: string
  color: string
  definition: string
  synonyms: string[]
  related: string[]
  visible: boolean
}

/** Палитра из CSS-переменных design-system */
export const PALETTE = [
  'var(--accent)',
  'var(--accent-hover)',
  'var(--cyan)',
  'var(--purple)',
  'var(--amber)',
  'var(--red)',
  'var(--green)',
  'var(--blue)',
]

interface ThesaurusState {
  entries: ThesaurusEntry[]
  addEntry: (word: string) => void
  setColor: (id: string, color: string) => void
  setDefinition: (id: string, definition: string) => void
  toggleVisible: (id: string) => void
  addTag: (id: string, kind: TagKind, value: string) => void
  removeTag: (id: string, kind: TagKind, value: string) => void
}

const MOCK_ENTRIES: ThesaurusEntry[] = [
  {
    id: 'th-1',
    word: 'emergence',
    color: 'var(--accent)',
    definition: 'The arising of novel properties in complex systems that are not present in individual parts.',
    synonyms: ['arising', 'appearance'],
    related: ['complexity', 'scaling'],
    visible: true,
  },
  {
    id: 'th-2',
    word: 'transformer',
    color: 'var(--amber)',
    definition: 'A neural network architecture based on self-attention, introduced in "Attention Is All You Need".',
    synonyms: ['model', 'architecture'],
    related: ['attention', 'encoder'],
    visible: true,
  },
  {
    id: 'th-3',
    word: 'attention',
    color: 'var(--purple)',
    definition: 'A mechanism that lets a model weigh the relevance of different input tokens.',
    synonyms: ['self-attention', 'focus'],
    related: ['transformer', 'query'],
    visible: false,
  },
]

let nextId = 100

export const useThesaurusStore = create<ThesaurusState>((set) => ({
  entries: MOCK_ENTRIES,

  addEntry: (word) =>
    set((s) => ({
      entries: [
        ...s.entries,
        {
          id: `th-${nextId++}`,
          word,
          color: PALETTE[s.entries.length % PALETTE.length],
          definition: '',
          synonyms: [],
          related: [],
          visible: true,
        },
      ],
    })),

  setColor: (id, color) =>
    set((s) => ({
      entries: s.entries.map((e) => (e.id === id ? { ...e, color } : e)),
    })),

  setDefinition: (id, definition) =>
    set((s) => ({
      entries: s.entries.map((e) => (e.id === id ? { ...e, definition } : e)),
    })),

  toggleVisible: (id) =>
    set((s) => ({
      entries: s.entries.map((e) =>
        e.id === id ? { ...e, visible: !e.visible } : e,
      ),
    })),

  addTag: (id, kind, value) =>
    set((s) => ({
      entries: s.entries.map((e) =>
        e.id === id && value && !e[kind].includes(value)
          ? { ...e, [kind]: [...e[kind], value] }
          : e,
      ),
    })),

  removeTag: (id, kind, value) =>
    set((s) => ({
      entries: s.entries.map((e) =>
        e.id === id ? { ...e, [kind]: e[kind].filter((t) => t !== value) } : e,
      ),
    })),
}))
