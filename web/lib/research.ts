import type { PaperId } from "./types";

export type Paper = {
  id: PaperId;
  authors: string;
  year: string;
  title: string;
  role: string;
  body: string;
  url: string;
};

export const PAPERS: Record<PaperId, Paper> = {
  "gayed-bilello-2016": {
    id: "gayed-bilello-2016",
    authors: "Gayed & Bilello",
    year: "2016",
    title: "Leverage for the Long Run",
    role: "Trend + leverage",
    body: "Hold leveraged equity while the index is above its long average; move to T-bills below it.",
    url: "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2741701",
  },
  "faber-2007": {
    id: "faber-2007",
    authors: "Faber",
    year: "2007",
    title: "A Quantitative Approach to Tactical Asset Allocation",
    role: "The moving-average filter",
    body: "The 10-month SMA rule: own an asset above its average, sit in T-bills below it.",
    url: "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461",
  },
  "moreira-muir-2017": {
    id: "moreira-muir-2017",
    authors: "Moreira & Muir",
    year: "2017",
    title: "Volatility-Managed Portfolios",
    role: "The risk budget",
    body: "Scale exposure by trailing realised variance instead of holding a fixed leverage all the time.",
    url: "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431",
  },
  "zarattini-antonacci-2024": {
    id: "zarattini-antonacci-2024",
    authors: "Zarattini & Antonacci",
    year: "2024",
    title: "A Century of Profitable Industry Trends",
    role: "Volatility-targeted trend",
    body: "Per-asset volatility targeting with trend filters across a century of industry portfolios.",
    url: "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4857230",
  },
};

export const REPLICATION = {
  label: "Nygård & Liukko (2026)",
  url: "https://diva-portal.org/smash/get/diva2:2077998/FULLTEXT01.pdf",
  body: "test a 3x Nasdaq-100 rule with a 200-day filter and an implied-volatility filter over 2001-2026: about 22% a year with a -64.8% drawdown. That is roughly buy-and-hold's 21% return with a much smaller drawdown — not a new source of alpha.",
};

export const COUNTER_EVIDENCE = [
  {
    label: "Cederburg et al. (2020)",
    url: "https://www.lehigh.edu/~xuy219/research/COWY.pdf",
    body: "find volatility management does not systematically beat unmanaged portfolios out of sample.",
  },
  {
    label: "Massaad et al. (2024)",
    url: "https://arxiv.org/abs/2412.14361",
    body: "find published trend results weaken under robust testing.",
  },
];
