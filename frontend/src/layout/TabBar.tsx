import type { ReactNode } from "react";
import { NavLink } from "react-router";
import "./TabBar.css";

// Each tab is a little patch sewn on (2026-11-25: the stock line icons stood apart from the
// patchwork). Cloth, a running stitch just inside its edge and a motif; TabBar.css colours them,
// linen when idle, denim with cream thread on the open tab.
const svgProps = {
  "aria-hidden": true,
  className: "tab-ico",
  width: 30,
  height: 30,
  viewBox: "0 0 32 32",
} as const;

const TABS: { to: string; label: string; icon: ReactNode }[] = [
  {
    to: "/",
    label: "오늘",
    // a round patch with a clock on it
    icon: (
      <svg {...svgProps}>
        <circle className="tab-ico__cloth" cx="16" cy="16" r="13" />
        <circle className="tab-ico__stitch" cx="16" cy="16" r="10.2" />
        <path className="tab-ico__motif" d="M16 10.5V16l3.6 2.4" />
      </svg>
    ),
  },
  {
    to: "/trips",
    label: "여행 원단",
    // a boarding pass, like the trip cards
    icon: (
      <svg {...svgProps}>
        <path
          className="tab-ico__cloth"
          d="M5 7h16.5a2.2 2.2 0 0 0 4.4 0H27a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-1.1a2.2 2.2 0 0 0-4.4 0H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2Z"
        />
        <path className="tab-ico__stitch" d="M23.7 10.5v11" />
        <path className="tab-ico__motif" d="M7.5 13.5h10M7.5 18.5h6.5" />
      </svg>
    ),
  },
  {
    to: "/patchwork",
    label: "패치 모음",
    // a square mend, cross-stitched at the corners
    icon: (
      <svg {...svgProps}>
        <rect
          className="tab-ico__cloth"
          x="5"
          y="5"
          width="22"
          height="22"
          rx="3"
          transform="rotate(-6 16 16)"
        />
        <rect
          className="tab-ico__stitch"
          x="8.2"
          y="8.2"
          width="15.6"
          height="15.6"
          rx="1.5"
          transform="rotate(-6 16 16)"
        />
        <path
          className="tab-ico__motif"
          d="M3.5 4.5l3 3M6.5 4.5l-3 3M25.5 4l3 3M28.5 4l-3 3M3.5 25l3 3M6.5 25l-3 3M25.5 24.5l3 3M28.5 24.5l-3 3"
        />
      </svg>
    ),
  },
];

export default function TabBar() {
  return (
    <nav className="tab-bar tp-pinked-top" aria-label="주요 메뉴">
      {/* NavLink = <a> that knows the current URL: it adds aria-current="page" and the
          "active" class when `to` matches. `end` on "/" stops it matching every path. */}
      {TABS.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          end={t.to === "/"}
          className="tab-bar__item"
        >
          {t.icon}
          {t.label}
        </NavLink>
      ))}
    </nav>
  );
}
