"use client";

import { Icon } from "@iconify/react";
import {
  ReactNode,
  useEffect,
  useState,
  useMemo,
  useRef,
  useLayoutEffect,
} from "react";
import { usePathname, useRouter } from "next/navigation";

type TabType = "queue" | "graph" | "search";

const TAB_ICON_MAP: Record<TabType, string> = {
  queue: "heroicons:queue-list-16-solid",
  graph: "ph:graph-bold",
  search: "material-symbols:search-rounded",
};

function Tab({
  activeTab,
  setActiveTab,
  tabValue,
}: {
  activeTab: TabType;
  setActiveTab: (tab: TabType) => void;
  tabValue: TabType;
}) {
  return (
    <button
      onClick={() => setActiveTab(tabValue)}
      aria-label={tabValue}
      className={`relative flex h-10 w-[60px] items-center justify-center rounded-[20px] text-xs font-bold transition-all duration-300 ease-in-out capitalize ${
        activeTab === tabValue
          ? "text-white"
          : "text-black/75 hover:bg-[#DDDDDD] hover:drop-shadow-md"
      }`}
    >
      <Icon
        icon={TAB_ICON_MAP[tabValue]}
        width={25}
        height={25}
        className="pointer-events-none"
      />
    </button>
  );
}

export default function TabPanel() {
  const router = useRouter();
  const pathname = usePathname();
  const contentRef = useRef<HTMLDivElement>(null);
  const [isTransitioning, setIsTransitioning] = useState(false);

  // Map routes to tab types
  const routeToTab = useMemo(
    () => ({
      "/queue": "queue" as TabType,
      "/graph": "graph" as TabType,
      "/search": "search" as TabType,
    }),
    [],
  );

  const tabToRoute = useMemo(
    () => ({
      queue: "/queue",
      graph: "/graph",
      search: "/search",
    }),
    [],
  );

  // Determine active tab based on current route
  const getActiveTabFromRoute = (): TabType => {
    return (routeToTab as Record<string, TabType>)[pathname] || "queue";
  };

  const [activeTab, setActiveTab] = useState<TabType>(getActiveTabFromRoute());

  // Update active tab when route changes
  useEffect(() => {
    const getActiveTab = () =>
      (routeToTab as Record<string, TabType>)[pathname] || "queue";
    const newTab = getActiveTab();

    if (newTab !== activeTab) {
      setIsTransitioning(true);
      setActiveTab(newTab);

      // Reset transition state after animation completes
      setTimeout(() => {
        setIsTransitioning(false);
      }, 300);
    }
  }, [pathname, routeToTab, activeTab]);

  // Handle tab switching and routing
  const handleTabChange = (tab: TabType) => {
    if (tab === activeTab) return;

    setIsTransitioning(true);
    setActiveTab(tab);

    const route = (tabToRoute as Record<TabType, string>)[tab];
    if (route && route !== pathname) {
      router.push(route);
    }

    // Reset transition state after animation completes
    setTimeout(() => {
      setIsTransitioning(false);
    }, 300);
  };

  // Calculate translate position for sliding animation
  const getTranslateX = () => {
    const tabIndex = ["queue", "graph", "search"].indexOf(activeTab);
    if (tabIndex === 0) return "translate-x-0";
    if (tabIndex === 1) return "translate-x-[75px]";
    if (tabIndex === 2) return "translate-x-[150px]";
    return "translate-x-0";
  };

  return (
    <div className="flex flex-col items-center">
      {/* Tab Navigation */}
      <div className="panel-dark flex gap-[15px] p-[5px] relative z-10 transition-all drop-shadow-lg duration-300 ease-in-out rounded-[25px]">
        {/* Sliding Black Pill */}
        {/* hover scale not working */}
        <div
          className={`absolute h-10 w-[60px] rounded-[20px] bg-black/75 transition-all duration-300 ease-in-out ${getTranslateX()} shadow-md !hover:scale-105`}
        />
        <Tab
          activeTab={activeTab}
          setActiveTab={handleTabChange}
          tabValue="queue"
        />
        <Tab
          activeTab={activeTab}
          setActiveTab={handleTabChange}
          tabValue="graph"
        />
        <Tab
          activeTab={activeTab}
          setActiveTab={handleTabChange}
          tabValue="search"
        />
      </div>
    </div>
  );
}
