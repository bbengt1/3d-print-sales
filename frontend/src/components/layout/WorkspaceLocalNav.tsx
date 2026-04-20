import { useLocation, useNavigate } from 'react-router-dom';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/Tabs';
import { getWorkspaceForPath, isWorkspaceLinkActive } from './workspaces';

export default function WorkspaceLocalNav() {
  const location = useLocation();
  const navigate = useNavigate();
  const workspace = getWorkspaceForPath(location.pathname);

  if (!workspace.localLinks.length) {
    return null;
  }

  const activeValue =
    workspace.localLinks.find((link) => {
      const prefixes = link.matchPrefixes ?? [link.to];
      return isWorkspaceLinkActive(location.pathname, prefixes);
    })?.to ?? workspace.localLinks[0]?.to ?? '';

  return (
    <div aria-label={`${workspace.label} navigation`}>
      <Tabs value={activeValue} onValueChange={(next) => navigate(next)}>
        <TabsList>
          {workspace.localLinks.map((link) => (
            <TabsTrigger key={link.to} value={link.to}>
              {link.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
    </div>
  );
}
