"use client";

import PoliciesPanel from "@/components/policies";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { withAdminAuth } from "@/app/(dashboard)/components/withAdminAuth";

const PoliciesPage = () => {
  const { accessToken, userRole } = useAuthorized();

  return (
    <PoliciesPanel
      accessToken={accessToken}
      userRole={userRole}
    />
  );
};

export default withAdminAuth(PoliciesPage);
