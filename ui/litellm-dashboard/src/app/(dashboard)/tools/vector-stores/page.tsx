"use client";

import VectorStoreManagement from "@/components/vector_store_management";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { withAdminAuth } from "@/app/(dashboard)/components/withAdminAuth";

const VectorStoresPage = () => {
  const { accessToken, userId, userRole } = useAuthorized();

  return <VectorStoreManagement accessToken={accessToken} userID={userId} userRole={userRole} />;
};

export default withAdminAuth(VectorStoresPage);
