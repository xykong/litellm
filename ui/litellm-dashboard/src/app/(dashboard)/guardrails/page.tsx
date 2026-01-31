"use client";

import GuardrailsPanel from "@/components/guardrails";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { withAdminAuth } from "@/app/(dashboard)/components/withAdminAuth";

const GuardrailsPage = () => {
  const { accessToken, userRole } = useAuthorized();

  return <GuardrailsPanel accessToken={accessToken} userRole={userRole} />;
};

export default withAdminAuth(GuardrailsPage);
