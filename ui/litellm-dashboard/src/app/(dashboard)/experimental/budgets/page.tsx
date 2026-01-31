"use client";

import BudgetPanel from "@/components/budgets/budget_panel";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { withAdminAuth } from "@/app/(dashboard)/components/withAdminAuth";

const BudgetsPage = () => {
  const { accessToken } = useAuthorized();

  return <BudgetPanel accessToken={accessToken} />;
};

export default withAdminAuth(BudgetsPage);
