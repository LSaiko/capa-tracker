// Seed shown when VITE_BASE is non-root (GitHub Pages) or the API is unreachable: six synthetic
// 21 CFR 820 nonconformances spread across all five board columns, NC-3 reopened after a
// not_effective verification. Bands follow app/rca.py's keyword heuristic on each description.
import type { Detail } from "./types";

export const SEED_REOPENS = 1;

export const seedDetails: Detail[] = [
  {
    nonconformance: {
      id: "NC-1",
      description:
        "Customer complaint (820.198 file C-2026-041): infusion pump door latch fails to engage on 3 of 12 units from lot L-2409; pump alarms 'door open' with the set correctly loaded.",
      source: "complaint",
      severity: "critical",
      detected_date: "2026-09-14",
      status: "open",
    },
    rca: null,
    why_flags: [],
    capa: null,
    checks: [],
    closure: null,
  },
  {
    nonconformance: {
      id: "NC-2",
      description:
        "Bracket torque out of spec on line 3 (14 of 40 units at 1.8 Nm vs 2.5 Nm nominal); work instruction WI-42 lacks a torque spec for the M4 fastener.",
      source: "internal",
      severity: "major",
      detected_date: "2026-09-03",
      status: "rca_in_progress",
    },
    rca: {
      nonconformance_id: "NC-2",
      method: "5-why",
      steps: [
        { question: "Why did the bracket torque go out of spec?", answer: "The operator used the driver's default setting" },
        { question: "Why did the operator use the default setting?", answer: "WI-42 does not state a torque value for the M4 fastener" },
        { question: "Why does WI-42 not state a torque value?", answer: "The torque requirement was never transferred from the drawing to the work instruction at design transfer" },
      ],
      suggested_category: "Method",
      confidence: 1,
      confidence_band: "HIGH",
      root_cause_text: "",
    },
    why_flags: [
      { reads_systemic: false, reason: "no systemic marker found; ask why again" },
      { reads_systemic: false, reason: "no systemic marker found; ask why again" },
      { reads_systemic: true, reason: "'never' names a missing system element (reads as root cause)" },
    ],
    capa: null,
    checks: [],
    closure: null,
  },
  {
    nonconformance: {
      id: "NC-3",
      description:
        "Supplier lot 7731 of PEEK raw material failed incoming inspection for particulate contamination; supplier certificate of conformance was accepted without the 820.50 receiving inspection sample.",
      source: "supplier",
      severity: "major",
      detected_date: "2026-08-11",
      status: "capa_assigned",
    },
    rca: {
      nonconformance_id: "NC-3",
      method: "fishbone",
      steps: [
        { category: "Material", cause: "Supplier changed the resin drying process without notification (no supplier change agreement)" },
        { category: "Method", cause: "Receiving inspection procedure allows C-of-C acceptance for 'approved' suppliers with no periodic sampling" },
      ],
      suggested_category: "Material",
      confidence: 0.75,
      confidence_band: "AMBIGUOUS",
      root_cause_text: "Supplier control procedure SOP-050 lacks a change-notification clause and periodic re-sampling (820.50(a)).",
    },
    why_flags: [],
    capa: {
      id: "CAPA-3",
      nonconformance_id: "NC-3",
      action_description: "Add change-notification clause to supplier quality agreement; resume 100% receiving inspection for lot 7731 replacements.",
      owner: "supplier-quality@example.com",
      due_date: "2026-09-01",
      status: "planned",
    },
    checks: [
      {
        capa_id: "CAPA-3",
        check_date: "2026-09-18",
        method: "Review of next three incoming PEEK lots",
        result: "not_effective",
        evidence_uri: "file://incoming-inspection-2026-09.xlsx",
      },
    ],
    closure: null,
  },
  {
    nonconformance: {
      id: "NC-4",
      description:
        "Internal audit finding A-26-07: operator on night shift skipped the inspection step for housing bore diameter on 22 units; records show no in-process inspection stamp (820.80(c)).",
      source: "audit",
      severity: "minor",
      detected_date: "2026-07-22",
      status: "effectiveness_pending",
    },
    rca: {
      nonconformance_id: "NC-4",
      method: "5-why",
      steps: [
        { question: "Why was the inspection step skipped?", answer: "The night shift ran with one operator covering two stations" },
        { question: "Why did one operator cover two stations?", answer: "The shift handover had no staffing check and the backup was not trained on the bore gauge" },
      ],
      suggested_category: "Manpower",
      confidence: 0.6,
      confidence_band: "AMBIGUOUS",
      root_cause_text: "Shift handover checklist lacks a minimum-staffing gate; cross-training matrix not maintained.",
    },
    why_flags: [
      { reads_systemic: false, reason: "no systemic marker found; ask why again" },
      { reads_systemic: true, reason: "'not trained' names a missing system element (reads as root cause)" },
    ],
    capa: {
      id: "CAPA-4",
      nonconformance_id: "NC-4",
      action_description: "Add minimum-staffing gate to the shift handover checklist; cross-train two backup operators on the bore gauge and update the training matrix.",
      owner: "production-lead@example.com",
      due_date: "2026-08-20",
      status: "planned",
    },
    checks: [
      {
        capa_id: "CAPA-4",
        check_date: "2026-09-19",
        method: "30-day post-implementation effectiveness review",
        result: "pending",
        evidence_uri: null,
      },
    ],
    closure: null,
  },
  {
    nonconformance: {
      id: "NC-5",
      description:
        "Cleanroom humidity excursion to 68% RH for 40 min in the ISO 7 gowning area (limit 60%); environmental monitoring alarm acknowledged but no product hold placed (820.70(c)).",
      source: "internal",
      severity: "major",
      detected_date: "2026-06-05",
      status: "closed",
    },
    rca: {
      nonconformance_id: "NC-5",
      method: "5-why",
      steps: [
        { question: "Why did the humidity exceed 60% RH?", answer: "The HVAC dehumidifier tripped during a storm-related power dip" },
        { question: "Why was no product hold placed?", answer: "The alarm response procedure does not define a hold threshold; there is no requirement to quarantine in-process product" },
      ],
      suggested_category: "Environment",
      confidence: 1,
      confidence_band: "HIGH",
      root_cause_text: "SOP-071 environmental alarm response lacks a product-hold decision rule.",
    },
    why_flags: [
      { reads_systemic: false, reason: "no systemic marker found; ask why again" },
      { reads_systemic: true, reason: "'no requirement' names a missing system element (reads as root cause)" },
    ],
    capa: {
      id: "CAPA-5",
      nonconformance_id: "NC-5",
      action_description: "Revise SOP-071 with a product-hold rule at 60% RH for >15 min; add UPS to the dehumidifier controller.",
      owner: "facilities@example.com",
      due_date: "2026-07-01",
      status: "done",
    },
    checks: [
      {
        capa_id: "CAPA-5",
        check_date: "2026-08-01",
        method: "30-day review of EM alarms and hold records",
        result: "effective",
        evidence_uri: "file://em-review-2026-08.pdf",
      },
    ],
    closure: {
      capa_id: "CAPA-5",
      closed_date: "2026-08-04",
      closed_by: "qa-manager",
      linked_requirement_ids: ["REQ-ENV-3", "RC-12"],
    },
  },
  {
    nonconformance: {
      id: "NC-6",
      description: "Three finished devices found with the label peeling at final packaging; no visible damage to the pouch.",
      source: "internal",
      severity: "minor",
      detected_date: "2026-09-18",
      status: "open",
    },
    rca: null,
    why_flags: [],
    capa: null,
    checks: [],
    closure: null,
  },
];
