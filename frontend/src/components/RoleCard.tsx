import type { RoleDescriptor } from "@/types";

export function RoleCard({ role, onSelect }: { role: RoleDescriptor; onSelect: () => void }) {
  return (
    <button className="role-card" onClick={onSelect} type="button">
      <div className="role-name">{role.label}</div>
      <div className="role-tagline">{role.tagline}</div>
    </button>
  );
}
