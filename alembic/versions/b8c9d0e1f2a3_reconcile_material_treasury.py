"""reconcile material inventory and guild treasury

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-06-22 18:00:00
"""

from collections.abc import Sequence

from alembic import op


revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RESOURCE_DEFINITIONS = (
    ("wood", ("wood",)),
    ("ore", ("ore", "stone")),
    ("crystals", ("gem", "essence", "crystal")),
)


def upgrade() -> None:
    connection = op.get_bind()
    for resource_column, families in RESOURCE_DEFINITIONS:
        family_list = ", ".join(f"'{family}'" for family in families)
        connection.exec_driver_sql(f"""
            WITH canonical AS (
                SELECT id
                FROM item_templates
                WHERE item_type = 'material' AND material_family IN ({family_list})
                ORDER BY item_level, id
                LIMIT 1
            ), inventory_totals AS (
                SELECT gi.guild_id, COALESCE(SUM(gi.quantity), 0) AS quantity
                FROM guild_inventory_items gi
                JOIN item_templates it ON it.id = gi.item_template_id
                WHERE it.item_type = 'material' AND it.material_family IN ({family_list})
                GROUP BY gi.guild_id
            ), missing AS (
                SELECT gr.guild_id, c.id AS item_template_id,
                       gr.{resource_column} - COALESCE(t.quantity, 0) AS quantity
                FROM guild_resources gr
                CROSS JOIN canonical c
                LEFT JOIN inventory_totals t ON t.guild_id = gr.guild_id
                WHERE gr.{resource_column} > COALESCE(t.quantity, 0)
            )
            INSERT INTO guild_inventory_items
                (guild_id, item_template_id, quantity, created_at, updated_at)
            SELECT guild_id, item_template_id, quantity, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM missing
            WHERE 1 = 1
            ON CONFLICT (guild_id, item_template_id)
            DO UPDATE SET quantity = guild_inventory_items.quantity + EXCLUDED.quantity,
                          updated_at = CURRENT_TIMESTAMP
        """)
        connection.exec_driver_sql(f"""
            UPDATE guild_resources
            SET {resource_column} = (
                    SELECT COALESCE(SUM(gi.quantity), 0)
                    FROM guild_inventory_items gi
                    JOIN item_templates it ON it.id = gi.item_template_id
                    WHERE gi.guild_id = guild_resources.guild_id
                      AND it.item_type = 'material' AND it.material_family IN ({family_list})
                ),
                updated_at = CURRENT_TIMESTAMP
            WHERE {resource_column} <> (
                    SELECT COALESCE(SUM(gi.quantity), 0)
                    FROM guild_inventory_items gi
                    JOIN item_templates it ON it.id = gi.item_template_id
                    WHERE gi.guild_id = guild_resources.guild_id
                      AND it.item_type = 'material' AND it.material_family IN ({family_list})
                )
        """)


def downgrade() -> None:
    # The migration preserves the largest pre-existing balance. It is intentionally irreversible.
    pass
