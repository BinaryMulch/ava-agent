Creating and managing skills:
When asked to create a new skill, add a capability, or teach yourself something new:

What skills are:
- Skills are markdown files in {repo_dir}/skills/ that extend your knowledge and capabilities
- Each skill is a .md file that gets automatically loaded into your instructions on every message
- Skills are hot-reloaded — no restart needed after creating or editing one
- Skills teach you workflows, conventions, and domain-specific knowledge

Creating a new skill:
1. Ask the user what the skill should cover and any specific preferences they have
2. Choose a descriptive filename using snake_case: {repo_dir}/skills/skill_name.md
3. Write the skill following this structure:
   - Start with a clear title line describing the skill's purpose
   - Use "When asked to..." or "When you need to..." to define triggers
   - Organize instructions as numbered steps for workflows, or bullet points for guidelines
   - Include specific commands, paths, and examples — not vague guidance
   - Add an "Important rules" or "Guidelines" section at the end for safety and best practices
4. Verify the file was created: cat {repo_dir}/skills/skill_name.md
5. List all current skills: ls -la {repo_dir}/skills/

Available placeholders (replaced at runtime):
- {repo_dir} — The path to the Ava Agent installation directory
- {service_name} — The systemd service name (default: ava-agent)

Guidelines for writing good skills:
- Be specific and actionable — include exact commands, not just descriptions
- Keep skills focused on one domain — don't combine unrelated topics
- Include safety rules (e.g., "always back up before editing", "confirm before deleting")
- Use the same tone as existing skills for consistency
- Avoid duplicating instructions that are already in other skills
- Keep skills concise — there is a token budget, and every skill adds to it

Editing existing skills:
- List all skills: ls {repo_dir}/skills/
- View a skill: cat {repo_dir}/skills/skill_name.md
- Edit in place using sed, or rewrite with cat << 'EOF' > {repo_dir}/skills/skill_name.md
- Always show the user the changes after editing

Removing skills:
- Only remove a skill when the user explicitly asks
- Confirm with the user before deleting: "This will remove the [skill name] skill. Confirm?"
- Delete: rm {repo_dir}/skills/skill_name.md