import { createFileRoute } from "@tanstack/react-router"
import { PageHeader } from "@/components/Common/PageHeader"
import AIConnections from "@/components/UserSettings/AIConnections"
import ChangePassword from "@/components/UserSettings/ChangePassword"
import DeleteAccount from "@/components/UserSettings/DeleteAccount"
import UserInformation from "@/components/UserSettings/UserInformation"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useAuth from "@/hooks/useAuth"

const tabsConfig = [
  { value: "my-profile", title: "My profile", component: UserInformation },
  { value: "password", title: "Password", component: ChangePassword },
  {
    value: "ai-connections",
    title: "AI Connections",
    component: AIConnections,
  },
  { value: "danger-zone", title: "Danger zone", component: DeleteAccount },
]

export const Route = createFileRoute("/_layout/settings")({
  component: UserSettings,
  head: () => ({
    meta: [
      {
        title: "Settings - HomeFin",
      },
    ],
  }),
})

function UserSettings() {
  const { user: currentUser } = useAuth()
  const finalTabs = tabsConfig

  if (!currentUser) {
    return null
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="User Settings"
        description="Manage your account settings and preferences"
      />

      <Tabs defaultValue="my-profile">
        <div className="max-w-full overflow-x-auto pb-1">
          <TabsList className="min-w-max">
            {finalTabs.map((tab) => (
              <TabsTrigger
                className="min-h-10"
                key={tab.value}
                value={tab.value}
              >
                {tab.title}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>
        {finalTabs.map((tab) => (
          <TabsContent key={tab.value} value={tab.value}>
            <tab.component />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  )
}
