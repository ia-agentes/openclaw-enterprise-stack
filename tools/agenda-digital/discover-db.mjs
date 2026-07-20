import sql from "mssql";

const env = process.env;
const type = (env.TICKETS_DB_TYPE || "").toLowerCase();

if (type !== "mssql") {
  throw new Error(`TICKETS_DB_TYPE precisa ser mssql para este script; atual=${type || "vazio"}`);
}

const sslMode = (env.TICKETS_DB_SSLMODE || "prefer").toLowerCase();
const config = {
  server: env.TICKETS_DB_HOST,
  port: Number(env.TICKETS_DB_PORT || 1433),
  database: env.TICKETS_DB_NAME,
  user: env.TICKETS_DB_USER,
  password: env.TICKETS_DB_PASSWORD,
  options: {
    encrypt: ["require", "verify-full", "verify-ca"].includes(sslMode),
    trustServerCertificate: !["verify-full", "verify-ca"].includes(sslMode),
    enableArithAbort: true,
  },
  pool: { max: 2, min: 0, idleTimeoutMillis: 10000 },
  connectionTimeout: 15000,
  requestTimeout: 30000,
};

const pool = await sql.connect(config);

try {
  const now = await pool
    .request()
    .query("select getdate() as server_time, db_name() as database_name");

  console.log(
    JSON.stringify(
      {
        ok: true,
        database: now.recordset[0].database_name,
        serverTime: now.recordset[0].server_time,
      },
      null,
      2,
    ),
  );

  const objects = await pool.request().query(`
    select top (200)
      table_schema as [schema],
      table_name as [name],
      table_type as [type]
    from information_schema.tables
    where table_type in ('BASE TABLE', 'VIEW')
    order by
      case
        when lower(table_name) like '%agenda%' or lower(table_name) like '%comunic%' then 0
        else 1
      end,
      table_schema,
      table_name
  `);

  console.log("\nOBJECTS");
  for (const row of objects.recordset) {
    console.log(`${row.type}\t${row.schema}.${row.name}`);
  }

  const candidates = objects.recordset
    .filter((row) => /agenda|comunic|diario|digital|atendimento|penden|status/i.test(`${row.schema}.${row.name}`))
    .slice(0, 30);

  console.log("\nCANDIDATE_COLUMNS");
  for (const item of candidates) {
    const columns = await pool
      .request()
      .input("schema", sql.NVarChar, item.schema)
      .input("name", sql.NVarChar, item.name)
      .query(`
        select column_name, data_type
        from information_schema.columns
        where table_schema = @schema and table_name = @name
        order by ordinal_position
      `);

    console.log(`\n${item.schema}.${item.name}`);
    console.log(columns.recordset.map((col) => `${col.column_name}:${col.data_type}`).join(", "));
  }
} finally {
  await pool.close();
}
