"use client";
import { useOrganizations } from "@/app/(dashboard)/hooks/organizations/useOrganizations";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import "@/i18n/config";
import {
  ApiOutlined,
  AppstoreOutlined,
  AuditOutlined,
  BankOutlined,
  BarChartOutlined,
  BgColorsOutlined,
  BlockOutlined,
  BookOutlined,
  CreditCardOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  FileTextOutlined,
  FolderOutlined,
  KeyOutlined,
  LineChartOutlined,
  PlayCircleOutlined,
  RobotOutlined,
  SafetyOutlined,
  SearchOutlined,
  SettingOutlined,
  TagsOutlined,
  TeamOutlined,
  ToolOutlined,
  UserOutlined,
} from "@ant-design/icons";
import type { MenuProps } from "antd";
import { ConfigProvider, Layout, Menu } from "antd";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { all_admin_roles, internalUserRoles, isAdminRole, rolesWithWriteAccess } from "../utils/roles";
import NewBadge from "./common_components/NewBadge";
import type { Organization } from "./networking";
import UsageIndicator from "./UsageIndicator";
const { Sider } = Layout;

// Define the props type
interface SidebarProps {
  setPage: (page: string) => void;
  defaultSelectedKey: string;
  collapsed?: boolean;
  enabledPagesInternalUsers?: string[] | null;
  enableProjectsUI?: boolean;
}

// Menu item configuration
interface MenuItem {
  key: string;
  page: string;
  label: string | React.ReactNode;
  labelKey?: string;
  roles?: string[];
  children?: MenuItem[];
  icon?: React.ReactNode;
  external_url?: string;
}

// Group configuration
interface MenuGroup {
  groupLabel: string;
  groupLabelKey?: string;
  items: MenuItem[];
  roles?: string[];
}

// Menu groups organized by category - defined outside component for export
const menuGroups: MenuGroup[] = [
  {
    groupLabel: "AI GATEWAY",
    groupLabelKey: "groupAiGateway",
    items: [
      {
        key: "api-keys",
        page: "api-keys",
        label: "Virtual Keys",
        labelKey: "virtualKeys",
        icon: <KeyOutlined />,
      },
      {
        key: "llm-playground",
        page: "llm-playground",
        label: "Playground",
        labelKey: "playground",
        icon: <PlayCircleOutlined />,
        roles: rolesWithWriteAccess,
      },
      {
        key: "models",
        page: "models",
        label: "Models + Endpoints",
        labelKey: "modelsEndpoints",
        icon: <BlockOutlined />,
        roles: rolesWithWriteAccess,
      },
      {
        key: "agents",
        page: "agents",
        label: "Agents",
        labelKey: "agents",
        icon: <RobotOutlined />,
        roles: rolesWithWriteAccess,
      },
      {
        key: "mcp-servers",
        page: "mcp-servers",
        label: "MCP Servers",
        labelKey: "mcpServers",
        icon: <ToolOutlined />,
      },
      {
        key: "guardrails",
        page: "guardrails",
        label: "Guardrails",
        labelKey: "guardrails",
        icon: <SafetyOutlined />,
        roles: all_admin_roles,
      },
      {
        key: "policies",
        page: "policies",
        label: "Policies",
        labelKey: "policies",
        icon: <AuditOutlined />,
        roles: all_admin_roles,
      },
      {
        key: "tools",
        page: "tools",
        label: "Tools",
        labelKey: "tools",
        icon: <ToolOutlined />,
        children: [
          {
            key: "search-tools",
            page: "search-tools",
            label: "Search Tools",
            labelKey: "searchTools",
            icon: <SearchOutlined />,
          },
          {
            key: "vector-stores",
            page: "vector-stores",
            label: "Vector Stores",
            labelKey: "vectorStores",
            icon: <DatabaseOutlined />,
          },
          {
            key: "tool-policies",
            page: "tool-policies",
            label: "Tool Policies",
            labelKey: "toolPolicies",
            icon: <SafetyOutlined />,
          },
        ],
      },
    ],
  },
  {
    groupLabel: "OBSERVABILITY",
    groupLabelKey: "groupObservability",
    items: [
      {
        key: "new_usage",
        page: "new_usage",
        icon: <BarChartOutlined />,
        roles: [...all_admin_roles, ...internalUserRoles],
        label: "Usage",
        labelKey: "usage",
      },
      {
        key: "logs",
        page: "logs",
        label: "Logs",
        labelKey: "logs",
        icon: <LineChartOutlined />,
      },
      {
        key: "guardrails-monitor",
        page: "guardrails-monitor",
        label: "Guardrails Monitor",
        labelKey: "guardrailsMonitor",
        icon: <SafetyOutlined />,
        roles: [...all_admin_roles, ...internalUserRoles],
      },
    ],
  },
  {
    groupLabel: "ACCESS CONTROL",
    groupLabelKey: "groupAccessControl",
    items: [
      {
        key: "teams",
        page: "teams",
        label: "Teams",
        labelKey: "teams",
        icon: <TeamOutlined />,
      },
      {
        key: "projects",
        page: "projects",
        label: "Projects",
        labelKey: "projects",
        icon: <FolderOutlined />,
        roles: all_admin_roles,
      },
      {
        key: "users",
        page: "users",
        label: "Internal Users",
        labelKey: "internalUsers",
        icon: <UserOutlined />,
        roles: all_admin_roles,
      },
      {
        key: "organizations",
        page: "organizations",
        label: "Organizations",
        labelKey: "organizations",
        icon: <BankOutlined />,
        roles: all_admin_roles,
      },
      {
        key: "access-groups",
        page: "access-groups",
        label: "Access Groups",
        labelKey: "accessGroups",
        icon: <BlockOutlined />,
        roles: all_admin_roles,
      },
      {
        key: "budgets",
        page: "budgets",
        label: "Budgets",
        labelKey: "budgets",
        icon: <CreditCardOutlined />,
        roles: all_admin_roles,
      },
    ],
  },
  {
    groupLabel: "DEVELOPER TOOLS",
    groupLabelKey: "groupDeveloperTools",
    items: [
      {
        key: "api_ref",
        page: "api_ref",
        label: "API Reference",
        labelKey: "apiReference",
        icon: <ApiOutlined />,
      },
      {
        key: "model-hub-table",
        page: "model-hub-table",
        label: "AI Hub",
        labelKey: "aiHub",
        icon: <AppstoreOutlined />,
      },
      {
        key: "learning-resources",
        page: "learning-resources",
        label: "Learning Resources",
        labelKey: "learningResources",
        icon: <BookOutlined />,
        external_url: "https://models.litellm.ai/cookbook",
      },
      {
        key: "experimental",
        page: "experimental",
        label: "Experimental",
        labelKey: "experimental",
        icon: <ExperimentOutlined />,
        children: [
          {
            key: "caching",
            page: "caching",
            label: "Caching",
            labelKey: "caching",
            icon: <DatabaseOutlined />,
            roles: all_admin_roles,
          },
          {
            key: "prompts",
            page: "prompts",
            label: "Prompts",
            labelKey: "prompts",
            icon: <FileTextOutlined />,
            roles: all_admin_roles,
          },
          {
            key: "transform-request",
            page: "transform-request",
            label: "API Playground",
            labelKey: "apiPlayground",
            icon: <ApiOutlined />,
            roles: [...all_admin_roles, ...internalUserRoles],
          },
          {
            key: "tag-management",
            page: "tag-management",
            label: "Tag Management",
            labelKey: "tagManagement",
            icon: <TagsOutlined />,
            roles: all_admin_roles,
          },
          {
            key: "claude-code-plugins",
            page: "claude-code-plugins",
            label: "Claude Code Plugins",
            labelKey: "claudeCodePlugins",
            icon: <ToolOutlined />,
            roles: all_admin_roles,
          },
          {
            key: "4",
            page: "usage",
            label: "Old Usage",
            labelKey: "oldUsage",
            icon: <BarChartOutlined />,
          }
        ],
      },
    ],
  },
  {
    groupLabel: "SETTINGS",
    groupLabelKey: "groupSettings",
    roles: all_admin_roles,
    items: [
      {
        key: "settings",
        page: "settings",
        label: "Settings",
        labelKey: "settings",
        icon: <SettingOutlined />,
        roles: all_admin_roles,
        children: [
          {
            key: "router-settings",
            page: "router-settings",
            label: "Router Settings",
            labelKey: "routerSettings",
            icon: <SettingOutlined />,
            roles: all_admin_roles,
          },
          {
            key: "logging-and-alerts",
            page: "logging-and-alerts",
            label: "Logging & Alerts",
            labelKey: "loggingAlerts",
            icon: <SettingOutlined />,
            roles: all_admin_roles,
          },
          {
            key: "admin-panel",
            page: "admin-panel",
            label: "Admin Settings",
            labelKey: "adminSettings",
            icon: <SettingOutlined />,
            roles: all_admin_roles,
          },
          {
            key: "cost-tracking",
            page: "cost-tracking",
            label: "Cost Tracking",
            labelKey: "costTracking",
            icon: <BarChartOutlined />,
            roles: all_admin_roles,
          },
          {
            key: "ui-theme",
            page: "ui-theme",
            label: "UI Theme",
            labelKey: "uiTheme",
            icon: <BgColorsOutlined />,
            roles: all_admin_roles,
          },
        ],
      },
    ],
  },
];

const Sidebar: React.FC<SidebarProps> = ({ setPage, defaultSelectedKey, collapsed = false, enabledPagesInternalUsers, enableProjectsUI }) => {
  const { userId, accessToken, userRole } = useAuthorized();
  const { data: organizations } = useOrganizations();
  const { t } = useTranslation("nav");

  // Check if user is an org_admin
  const isOrgAdmin = useMemo(() => {
    if (!userId || !organizations) return false;
    return organizations.some((org: Organization) =>
      org.members?.some((member) => member.user_id === userId && member.user_role === "org_admin"),
    );
  }, [userId, organizations]);

  // Navigate to page helper
  const navigateToPage = (page: string) => {
    const newSearchParams = new URLSearchParams(window.location.search);
    newSearchParams.set("page", page);
    window.history.pushState(null, "", `?${newSearchParams.toString()}`);
    setPage(page);
  };

  // Filter items based on user role and enabled pages for internal users
  const filterItemsByRole = (items: MenuItem[]): MenuItem[] => {
    const isAdmin = isAdminRole(userRole);

    // Debug logging
    if (enabledPagesInternalUsers !== null && enabledPagesInternalUsers !== undefined) {
      console.log("[LeftNav] Filtering with enabled pages:", {
        userRole,
        isAdmin,
        enabledPagesInternalUsers,
      });
    }

    return items
      .map((item) => ({
        ...item,
        children: item.children ? filterItemsByRole(item.children) : undefined,
      }))
      .filter((item) => {
        // Special handling for organizations menu item - allow org_admins
        if (item.key === "organizations") {
          const hasRoleAccess = !item.roles || item.roles.includes(userRole) || isOrgAdmin;
          if (!hasRoleAccess) return false;

          // Check enabled pages for internal users (non-admins)
          if (!isAdmin && enabledPagesInternalUsers !== null && enabledPagesInternalUsers !== undefined) {
            const isIncluded = enabledPagesInternalUsers.includes(item.page);
            console.log(`[LeftNav] Page "${item.page}" (${item.key}): ${isIncluded ? "VISIBLE" : "HIDDEN"}`);
            return isIncluded;
          }
          return true;
        }

        // Hide Projects page if enableProjectsUI is not enabled
        if (item.key === "projects" && !enableProjectsUI) return false;

        // Existing role check
        if (item.roles && !item.roles.includes(userRole)) return false;

        // Check enabled pages for internal users (non-admins)
        if (!isAdmin && enabledPagesInternalUsers !== null && enabledPagesInternalUsers !== undefined) {
          // If item has children, check if any children are visible
          if (item.children && item.children.length > 0) {
            const hasVisibleChildren = item.children.some((child) =>
              enabledPagesInternalUsers.includes(child.page)
            );
            if (hasVisibleChildren) {
              console.log(`[LeftNav] Parent "${item.page}" (${item.key}): VISIBLE (has visible children)`);
              return true;
            }
          }

          const isIncluded = enabledPagesInternalUsers.includes(item.page);
          console.log(`[LeftNav] Page "${item.page}" (${item.key}): ${isIncluded ? "VISIBLE" : "HIDDEN"}`);
          return isIncluded;
        }

        return true;
      });
  };

  const resolveLabel = (item: MenuItem): React.ReactNode => {
    const translated = item.labelKey ? t(item.labelKey) : (item.label as string);
    if (item.key === "projects") {
      return (
        <span className="flex items-center gap-2">
          {translated} <NewBadge />
        </span>
      );
    }
    if (item.key === "settings") {
      return (
        <span className="flex items-center gap-2">
          {translated} <NewBadge />
        </span>
      );
    }
    if (item.key === "admin-panel") {
      return (
        <span className="flex items-center gap-2">
          {translated} <NewBadge dot><span /></NewBadge>
        </span>
      );
    }
    return translated;
  };

  // Build menu items with groups
  const buildMenuItems = (): MenuProps["items"] => {
    const items: MenuProps["items"] = [];

    menuGroups.forEach((group) => {
      // Check if group has role restriction
      if (group.roles && !group.roles.includes(userRole)) {
        return;
      }

      const filteredItems = filterItemsByRole(group.items);
      if (filteredItems.length === 0) return;

      const groupLabel = group.groupLabelKey ? t(group.groupLabelKey) : group.groupLabel;


      items.push({
        type: "group",
        label: collapsed ? null : (
          <span
            style={{
              fontSize: "10px",
              fontWeight: 600,
              color: "#6b7280",
              letterSpacing: "0.05em",
              padding: "12px 0 4px 12px",
              display: "block",
              marginBottom: "2px",
            }}
          >
            {groupLabel}
          </span>
        ),
        children: filteredItems.map((item) => ({
          key: item.key,
          icon: item.icon,
          label: resolveLabel(item),
          children: item.children?.map((child) => ({
            key: child.key,
            icon: child.icon,
            label: resolveLabel(child),
            onClick: () => {
              if (child.external_url) {
                window.open(child.external_url, "_blank");
              } else {
                navigateToPage(child.page);
              }
            },
          })),
          onClick: !item.children
            ? () => {
              if (item.external_url) {
                window.open(item.external_url, "_blank");
              } else {
                navigateToPage(item.page);
              }
            }
            : undefined,
        })),
      });
    });

    return items;
  };

  // Find selected menu key
  const findMenuItemKey = (page: string): string => {
    for (const group of menuGroups) {
      for (const item of group.items) {
        if (item.page === page) return item.key;
        if (item.children) {
          const child = item.children.find((c) => c.page === page);
          if (child) return child.key;
        }
      }
    }
    return "api-keys";
  };

  const selectedMenuKey = findMenuItemKey(defaultSelectedKey);

  return (
    <Layout>
      <Sider
        theme="light"
        width={220}
        collapsed={collapsed}
        collapsedWidth={80}
        collapsible
        trigger={null}
        style={{
          transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
          position: "relative",
        }}
      >
        <ConfigProvider
          theme={{
            components: {
              Menu: {
                iconSize: 15,
                fontSize: 13,
                itemMarginInline: 4,
                itemPaddingInline: 8,
                itemHeight: 30,
                itemBorderRadius: 6,
                subMenuItemBorderRadius: 6,
                groupTitleFontSize: 10,
                groupTitleLineHeight: 1.5,
              },
            },
          }}
        >
          <Menu
            mode="inline"
            selectedKeys={[selectedMenuKey]}
            defaultOpenKeys={[]}
            inlineCollapsed={collapsed}
            className="custom-sidebar-menu"
            style={{
              borderRight: 0,
              backgroundColor: "transparent",
              fontSize: "13px",
              paddingTop: "4px",
            }}
            items={buildMenuItems()}
          />
        </ConfigProvider>
        {isAdminRole(userRole) && !collapsed && <UsageIndicator accessToken={accessToken} width={220} />}
      </Sider>
    </Layout>
  );
};

export default Sidebar;

// Also export menuGroups for advanced use cases
export { menuGroups };
