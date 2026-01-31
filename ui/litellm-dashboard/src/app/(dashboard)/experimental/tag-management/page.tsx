"use client";

import TagManagement from "@/components/tag_management";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { withAdminAuth } from "@/app/(dashboard)/components/withAdminAuth";

const TagManagementPage = () => {
  const { accessToken, userId, userRole } = useAuthorized();

  return <TagManagement accessToken={accessToken} userID={userId} userRole={userRole} />;
};

export default withAdminAuth(TagManagementPage);
