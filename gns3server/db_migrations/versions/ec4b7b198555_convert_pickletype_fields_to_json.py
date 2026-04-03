"""convert PickleType fields to JSON

Revision ID: ec4b7b198555
Revises: 20260303_create_llm_model_configs
Create Date: 2026-04-03 19:51:06.173013

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ec4b7b198555'
down_revision = '20260303_create_llm_model_configs'
branch_labels = None
depends_on = None


def convert_pickle_to_json(conn, table_name: str, column_name: str) -> None:
    """
    Convert a PickleType column to JSON for all rows in a table.
    """

    import pickle
    import json

    result = conn.execute(sa.text(f"SELECT template_id, {column_name} FROM {table_name}"))
    for row in result:
        column_data = getattr(row, column_name)
        if column_data:
            # Unpickle and convert to JSON
            data = pickle.loads(column_data)
            if data:
                json_data = json.dumps(data)
                conn.execute(
                    sa.text(f"UPDATE {table_name} SET {column_name} = :data WHERE template_id = :template_id"),
                    {"data": json_data, "template_id": row.template_id}
                )
            else:
                # Set NULL if there is no data to be converted
                conn.execute(
                    sa.text(f"UPDATE {table_name} SET {column_name} = NULL WHERE template_id = :template_id"),
                    {"template_id": row.template_id}
                )


def convert_json_to_pickle(conn, table_name: str, column_name: str) -> None:
    """
    Convert a JSON column to PickleType for all rows in a table.
    """

    import pickle
    import json

    result = conn.execute(sa.text(f"SELECT template_id, {column_name} FROM {table_name}"))
    for row in result:
        column_data = getattr(row, column_name)
        if column_data:
            # Parse JSON and convert to pickle
            data = json.loads(column_data)
            if data:
                pickle_data = pickle.dumps(data)
                conn.execute(
                    sa.text(f"UPDATE {table_name} SET {column_name} = :data WHERE template_id = :template_id"),
                    {"data": pickle_data, "template_id": row.template_id}
                )
            else:
                # Set NULL if there is no data to be converted
                conn.execute(
                    sa.text(f"UPDATE {table_name} SET {column_name} = NULL WHERE template_id = :template_id"),
                    {"template_id": row.template_id}
                )


def upgrade() -> None:

    # Get connection
    conn = op.get_bind()

    # Convert PickleType fields to JSON
    convert_pickle_to_json(conn, "cloud_templates", "ports_mapping")
    convert_pickle_to_json(conn, "docker_templates", "extra_volumes")
    convert_pickle_to_json(conn, "docker_templates", "custom_adapters")
    convert_pickle_to_json(conn, "ethernet_hub_templates", "ports_mapping")
    convert_pickle_to_json(conn, "ethernet_switch_templates", "ports_mapping")
    convert_pickle_to_json(conn, "qemu_templates", "custom_adapters")
    convert_pickle_to_json(conn, "virtualbox_templates", "custom_adapters")
    convert_pickle_to_json(conn, "vmware_templates", "custom_adapters")

    with op.batch_alter_table('cloud_templates') as batch_op:
        batch_op.alter_column('ports_mapping', type_=sa.JSON())
    with op.batch_alter_table('docker_templates') as batch_op:
        batch_op.alter_column('extra_volumes', type_=sa.JSON())
        batch_op.alter_column('custom_adapters', type_=sa.JSON())
    with op.batch_alter_table('ethernet_hub_templates') as batch_op:
        batch_op.alter_column('ports_mapping', type_=sa.JSON())
    with op.batch_alter_table('ethernet_switch_templates') as batch_op:
        batch_op.alter_column('ports_mapping', type_=sa.JSON())
    with op.batch_alter_table('qemu_templates') as batch_op:
        batch_op.alter_column('custom_adapters', type_=sa.JSON())
    with op.batch_alter_table('virtualbox_templates') as batch_op:
        batch_op.alter_column('custom_adapters', type_=sa.JSON())
    with op.batch_alter_table('vmware_templates') as batch_op:
        batch_op.alter_column('custom_adapters', type_=sa.JSON())

def downgrade() -> None:

    # Get connection
    conn = op.get_bind()

    # Convert JSON fields back to PickleType
    convert_json_to_pickle(conn, "cloud_templates", "ports_mapping")
    convert_json_to_pickle(conn, "docker_templates", "extra_volumes")
    convert_json_to_pickle(conn, "docker_templates", "custom_adapters")
    convert_json_to_pickle(conn, "ethernet_hub_templates", "ports_mapping")
    convert_json_to_pickle(conn, "ethernet_switch_templates", "ports_mapping")
    convert_json_to_pickle(conn, "qemu_templates", "custom_adapters")
    convert_json_to_pickle(conn, "virtualbox_templates", "custom_adapters")
    convert_json_to_pickle(conn, "vmware_templates", "custom_adapters")

    with op.batch_alter_table('cloud_templates') as batch_op:
        batch_op.alter_column('ports_mapping', type_=sa.PickleType())
    with op.batch_alter_table('docker_templates') as batch_op:
        batch_op.alter_column('extra_volumes', type_=sa.PickleType())
        batch_op.alter_column('custom_adapters', type_=sa.PickleType())
    with op.batch_alter_table('ethernet_hub_templates') as batch_op:
        batch_op.alter_column('ports_mapping', type_=sa.PickleType())
    with op.batch_alter_table('ethernet_switch_templates') as batch_op:
        batch_op.alter_column('ports_mapping', type_=sa.PickleType())
    with op.batch_alter_table('qemu_templates') as batch_op:
        batch_op.alter_column('custom_adapters', type_=sa.PickleType())
    with op.batch_alter_table('virtualbox_templates') as batch_op:
        batch_op.alter_column('custom_adapters', type_=sa.PickleType())
    with op.batch_alter_table('vmware_templates') as batch_op:
        batch_op.alter_column('custom_adapters', type_=sa.PickleType())
