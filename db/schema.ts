import { sqliteTable, text, integer } from 'drizzle-orm/sqlite-core';
export const workspaces=sqliteTable('workspaces',{
 userId:text('user_id').primaryKey(),stateJson:text('state_json').notNull(),revision:integer('revision').notNull().default(1),updatedAt:text('updated_at').notNull(),
});
export const appUsers=sqliteTable('app_users',{
 userId:text('user_id').primaryKey(),email:text('email').notNull(),displayName:text('display_name').notNull(),role:text('role').notNull().default('user'),status:text('status').notNull().default('active'),joinedAt:text('joined_at').notNull(),lastSeenAt:text('last_seen_at').notNull(),accessRevision:integer('access_revision').notNull().default(1),
});
export const appSettings=sqliteTable('app_settings',{key:text('key').primaryKey(),value:text('value').notNull()});
export const adminAudit=sqliteTable('admin_audit',{id:integer('id').primaryKey({autoIncrement:true}),actorId:text('actor_id').notNull(),targetId:text('target_id').notNull(),action:text('action').notNull(),detail:text('detail').notNull(),createdAt:text('created_at').notNull()});
