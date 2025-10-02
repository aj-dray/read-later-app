// import bcrypt from "bcrypt";
// import { title } from "node:process";
// import postgres from "postgres";

// // === USERS === //

// const users = [
//   {
//     id : "550e8400-e29b-41d4-a716-446655440000",
//     username: "test",
//     email: "fake@email.com",
//     password: "password",
//   },
// ];

// const sql = postgres(process.env.POSTGRES_URL!, { ssl: "require" });

// async function seedUsers() {
//   await sql`CREATE EXTENSION IF NOT EXISTS "uuid-ossp"`;
//   await sql`
//     CREATE TABLE IF NOT EXISTS users (
//     id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
//     username TEXT UNIQUE NOT NULL,
//     email TEXT UNIQUE,
//     password_hash TEXT NOT NULL,
//     created_at TIMESTAMPTZ NOT NULL DEFAULT now()
//     );
//   `;

//   const insertUsers = await Promise.all(
//     users.map(async (user) => {
//       const hashedPassword = await bcrypt.hash(user.password, 10);
//       return sql`
//         INSERT INTO users (id, name, email, password)
//         VALUES (${user.username}, ${user.email}, ${hashedPassword})
//         ON CONFLICT (id) DO NOTHING;
//       `;
//     }),
//   );

//   return insertUsers;
// }

// // === ITEMS === //

// async function seedItems() {
//   await sql`CREATE EXTENSION IF NOT EXISTS "uuid-ossp"`;
//   await sql`

//     CREATE TYPE item_status AS ENUM ('saved','queued','paused','completed','dismissed');

//     CREATE TABLE IF NOT EXISTS items (
//     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
//     user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
//     url TEXT NOT NULL,
//     canonical_url TEXT,                            -- strips down to basic
//     url_hash TEXT GENERATED ALWAYS AS (md5(coalesce(canonical_url,url))) STORED,
//     title TEXT,
//     source_site TEXT,
//     favicon_url TEXT,
//     read_duration_seconds INT,                    -- estimate
//     status item_status NOT NULL DEFAULT 'saved',
//     summary TEXT,
//     expiry_score REAL,                             -- 0..1
//     markdown_content TEXT,                         -- editable
//     html_raw TEXT,                                 -- optional raw capture
//     content_tsv tsvector,                          -- for FTS
//     embedding vector(1024),                        -- set dim to your model
//     embedding_model TEXT,
//     embedding_updated_at TIMESTAMPTZ,
//     content_updated_at TIMESTAMPTZ,
//     created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
//     completed_at TIMESTAMPTZ,
//     dismissed_at TIMESTAMPTZ
//     );

//     -- Prevent url dupes per user
//     CREATE UNIQUE INDEX uniq_item_per_user_url ON items(user_id, url_hash) WHERE deleted_at IS NULL;
//   `;

//   const insertItems = await Promise.all(
//     items.map(async (item) => {
//       return sql`
//         INSERT INTO items (
//           user_id, url, canonical_url, title, source_site, favicon_url,
//           read_duration_seconds, status, summary, expiry_score, markdown_content
//         )
//         VALUES (
//           ${item.user_id}, ${item.url}, ${item.canonical_url}, ${item.title},
//           ${item.source_site}, ${item.favicon_url}, ${item.read_duration_seconds},
//           ${item.status}, ${item.summary}, ${item.expiry_score}, ${item.markdown_content}
//         )
//         ON CONFLICT (user_id, url_hash) DO NOTHING;
//       `;
//     }),
//   );

//   return insertItems;
// }

// async function main() {
//   await seedUsers();
//   await seedItems();
//   await sql.end();
// }

// main().catch((err) => {
//   console.error(
//     "An error occurred while attempting to seed the database:",
//     err,
//   );
// });

// export { seedUsers, seedItems };
