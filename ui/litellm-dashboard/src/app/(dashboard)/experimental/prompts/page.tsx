"use client";

import PromptsPanel from "@/components/prompts";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { withAdminAuth } from "@/app/(dashboard)/components/withAdminAuth";

const PromptsPage = () => {
  const { accessToken, userRole } = useAuthorized();

  return <PromptsPanel accessToken={accessToken} userRole={userRole} />;
};

export default withAdminAuth(PromptsPage);
