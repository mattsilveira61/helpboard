"""respostas prontas e fechamento automatico

Revision ID: 363fb273d91b
Revises: d758ea9f0c78
Create Date: 2026-10-16 15:45:25.411692

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

OLD_ACTIONS = ['CRIADO', 'EDITADO', 'STATUS_ALTERADO', 'ATRIBUIDO', 'PRIORIDADE_ALTERADA', 'CATEGORIA_ALTERADA',
               'SOLUCAO_REGISTRADA', 'REABERTO', 'ARQUIVADO', 'AVALIADO']
NEW_ACTIONS = OLD_ACTIONS + ['FECHADO_AUTOMATICAMENTE']
CHECK = op.f('ck_ticket_history_history_action')


def _set_history_actions(actions: list[str], length: int) -> None:
    op.drop_constraint(CHECK, 'ticket_history', type_='check')
    op.alter_column('ticket_history', 'action', type_=sa.String(length), existing_nullable=False)
    op.create_check_constraint(CHECK, 'ticket_history', "action IN (%s)" % ", ".join(f"'{a}'" for a in actions))


# revision identifiers, used by Alembic.
revision: str = '363fb273d91b'
down_revision: Union[str, Sequence[str], None] = 'd758ea9f0c78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('canned_responses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=80), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('length(trim(body)) > 0', name=op.f('ck_canned_responses_body_not_empty')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_canned_responses')),
    sa.UniqueConstraint('title', name=op.f('uq_canned_responses_title'))
    )
    # FECHADO_AUTOMATICAMENTE tem 23 letras: a coluna (VARCHAR do tamanho do maior valor) precisa crescer
    _set_history_actions(NEW_ACTIONS, 23)


def downgrade() -> None:
    op.execute("UPDATE ticket_history SET action = 'STATUS_ALTERADO' WHERE action = 'FECHADO_AUTOMATICAMENTE'")
    _set_history_actions(OLD_ACTIONS, 19)
    op.drop_table('canned_responses')
