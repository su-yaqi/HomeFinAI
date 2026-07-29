import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { Suspense, useState } from "react"

import { type UserPublic, UsersService } from "@/client"
import AddUser from "@/components/Admin/AddUser"
import { columns, type UserTableData } from "@/components/Admin/columns"
import { UserActionsMenu } from "@/components/Admin/UserActionsMenu"
import { DataTable } from "@/components/Common/DataTable"
import { PageHeader } from "@/components/Common/PageHeader"
import PendingUsers from "@/components/Pending/PendingUsers"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { homefinApi } from "@/features/homefin/api"
import useAuth from "@/hooks/useAuth"

function getUsersQueryOptions(page: number, pageSize: number) {
  return {
    queryFn: () => homefinApi.readUsers({ page, page_size: pageSize }),
    queryKey: ["users", page, pageSize],
  }
}

export const Route = createFileRoute("/_layout/system/accounts")({
  component: AccountsPage,
  beforeLoad: async () => {
    const user = await UsersService.readUserMe()
    if (!user.is_superuser) {
      throw redirect({
        to: "/",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Accounts - HomeFin",
      },
    ],
  }),
})

function UsersTableContent() {
  const { user: currentUser } = useAuth()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const { data: users } = useSuspenseQuery(getUsersQueryOptions(page, pageSize))

  const tableData: UserTableData[] = users.data.map((user: UserPublic) => ({
    ...user,
    isCurrentUser: currentUser?.id === user.id,
  }))

  return (
    <DataTable
      columns={columns}
      data={tableData}
      totalCount={users.count}
      page={page}
      pageSize={pageSize}
      onPageChange={setPage}
      onPageSizeChange={(nextPageSize) => {
        setPage(1)
        setPageSize(nextPageSize)
      }}
      mobileEmptyMessage="No accounts found."
      renderMobileCard={(user) => (
        <Card className="gap-4 py-4 shadow-none">
          <CardContent className="space-y-4 px-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="break-words font-semibold">{user.login_name}</p>
                  {user.isCurrentUser ? (
                    <Badge variant="outline">You</Badge>
                  ) : null}
                </div>
                <p className="break-all text-sm text-muted-foreground">
                  {user.email}
                </p>
              </div>
              <UserActionsMenu user={user} />
            </div>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div className="min-w-0">
                <dt className="text-xs text-muted-foreground">Full name</dt>
                <dd className="break-words">{user.full_name || "N/A"}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Role</dt>
                <dd>{user.is_superuser ? "Superuser" : "User"}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Status</dt>
                <dd>{user.is_active ? "Active" : "Inactive"}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>
      )}
    />
  )
}

function UsersTable() {
  return (
    <Suspense fallback={<PendingUsers />}>
      <UsersTableContent />
    </Suspense>
  )
}

function AccountsPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Accounts"
        description="Manage login names, status, and privileges for system users."
        actions={<AddUser />}
      />
      <UsersTable />
    </div>
  )
}
