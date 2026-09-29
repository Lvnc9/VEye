/**
 * The Tiptap extensions of the تشریحی بلند editor — exactly the set the server's whitelist
 * (`rich_content.py`) accepts and the PDF renderer (`richtext.py`) prints, and nothing more:
 * whatever Word or a web page pastes in that is outside it is dropped by the schema rather than
 * refused at save time.
 */
import { Extension, Node, mergeAttributes } from "@tiptap/core";
import { ListItem } from "@tiptap/extension-list";
import { Table, TableCell, TableHeader, TableRow } from "@tiptap/extension-table";
import TextAlign from "@tiptap/extension-text-align";
import { TextStyle } from "@tiptap/extension-text-style";
import { Placeholder } from "@tiptap/extensions";
import StarterKit from "@tiptap/starter-kit";
import { MAX_INDENT, fontSizeFromCss, isAllowedLink, paletteColor } from "@/lib/rich-doc";

/** Font size (whole points from the offered list) and colour (the fixed palette) on the `textStyle` mark. */
const PrintStyle = Extension.create({
  name: "printStyle",
  addGlobalAttributes() {
    return [
      {
        types: ["textStyle"],
        attributes: {
          fontSize: {
            default: null,
            parseHTML: (element: HTMLElement) => fontSizeFromCss(element.style.fontSize),
            renderHTML: (attributes: Record<string, unknown>) =>
              attributes.fontSize ? { style: `font-size: ${attributes.fontSize}pt` } : {},
          },
          color: {
            default: null,
            parseHTML: (element: HTMLElement) => paletteColor(element.style.color),
            renderHTML: (attributes: Record<string, unknown>) =>
              attributes.color ? { style: `color: ${attributes.color}` } : {},
          },
        },
      },
    ];
  },
});

/** A paragraph's or heading's indent, 0–6 steps (the printer moves the right edge 24 pt per step). */
const Indent = Extension.create({
  name: "indent",
  addGlobalAttributes() {
    return [
      {
        types: ["paragraph", "heading"],
        attributes: {
          indent: {
            default: 0,
            parseHTML: (element: HTMLElement) => {
              const value = Number.parseInt(element.getAttribute("data-indent") ?? "0", 10);
              return Number.isFinite(value) ? Math.min(Math.max(value, 0), MAX_INDENT) : 0;
            },
            renderHTML: (attributes: Record<string, unknown>) =>
              attributes.indent ? { "data-indent": String(attributes.indent) } : {},
          },
        },
      },
    ];
  },
});

/** A forced page break — drawn as a dashed rule with a label (see globals.css). */
const PageBreak = Node.create({
  name: "pageBreak",
  group: "block",
  atom: true,
  selectable: true,
  parseHTML() {
    return [{ tag: "div[data-page-break]" }];
  },
  renderHTML() {
    return ["div", mergeAttributes({ "data-page-break": "", class: "rich-page-break" })];
  },
});

// A cell holds text, headings and lists — no nested tables, rules or page breaks (the printer draws no
// merged cells either: a colspan / rowspan from a paste is read as 1 and the table is repaired).
const CELL_CONTENT = "(paragraph | heading | bulletList | orderedList)+";
const unmerged = {
  colspan: { default: 1, parseHTML: () => 1, renderHTML: () => ({}) },
  rowspan: { default: 1, parseHTML: () => 1, renderHTML: () => ({}) },
};

const Cell = TableCell.extend({
  content: CELL_CONTENT,
  addAttributes() {
    return { ...this.parent?.(), ...unmerged };
  },
});

const HeaderCell = TableHeader.extend({
  content: CELL_CONTENT,
  addAttributes() {
    return { ...this.parent?.(), ...unmerged };
  },
});

// A list item is a paragraph followed by paragraphs and nested lists.
const Item = ListItem.extend({ content: "paragraph (paragraph | bulletList | orderedList)*" });

export function richExtensions(placeholder = "متن را اینجا بنویسید…") {
  return [
    StarterKit.configure({
      heading: { levels: [1, 2, 3] },
      blockquote: false,
      code: false,
      codeBlock: false,
      listItem: false,
      link: {
        openOnClick: false,
        autolink: true,
        linkOnPaste: true,
        defaultProtocol: "https",
        protocols: ["http", "https", "mailto"],
        isAllowedUri: (url: string) => isAllowedLink(url),
        HTMLAttributes: { rel: "noopener noreferrer", target: "_blank" },
      },
    }),
    Item,
    TextStyle,
    PrintStyle,
    Indent,
    PageBreak,
    TextAlign.configure({ types: ["heading", "paragraph"], alignments: ["right", "center", "left", "justify"], defaultAlignment: "right" }),
    Table.configure({ resizable: true, cellMinWidth: 40 }),
    TableRow,
    Cell,
    HeaderCell,
    Placeholder.configure({ placeholder }),
  ];
}
