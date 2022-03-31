from ast import Lambda
from random import randint
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta, datetime, date


class TrainingCourse(models.Model):
    _name = 'training.course'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Training Kursus'

    def get_default_color(self):
        return randint(1, 11)
    
    name = fields.Char(string='Judul', required=True, tracking=True)
    description = fields.Text(string='Keterangan', tracking=True)
    user_id = fields.Many2one('res.users', string="Penanggung Jawab", tracking=True)
    session_line = fields.One2many('training.session', 'course_id', string='Sesi', tracking=True)
    product_ids = fields.Many2many('product.product', 'course_product_rel', 'course_id', 'product_id', 'Cendera Mata', tracking=True)
    ref = fields.Char(string='Referensi', readonly=True, default='/')
    level = fields.Selection([('basic', 'Dasar'), ('advanced', 'Lanjutan')], string='Tingkatan', default='basic')
    color = fields.Integer('Warna', default=get_default_color)
    email = fields.Char(string="Email", related='user_id.login')
    total_hari = fields.Integer(compute='_compute_total_hari', string='Total Hari')
    total_peserta = fields.Integer(compute='_compute_total_peserta', string='Total Peserta')
    harga_kursus = fields.Monetary('Harga Kursus')
    currency_id = fields.Many2one('res.currency', string='Mata Uang', default=lambda self : self.env.company.currency_id)
    total_pendapatan = fields.Monetary(compute='_compute_total_pendapatan', string='Total Pendapatan')
    attendees_ids = fields.Many2many('training.attendee', compute='_list_peserta', string='Daftar Peserta')
    attendees_line = fields.One2many(comodel_name="training.attendee", inverse_name="course_id")

    def action_list_peserta(self):
        result = []
        for rec in self:
            for session in rec.session_line:
                for peserta in session.attendee_ids:
                    print("======================= hasil", peserta.name, peserta.id)
                    result.append(peserta.id)
                rec.write({'attendees_line': [(6, 0, result)]})

    def _list_peserta(self):
        result = []
        for rec in self:
            for session in rec.session_line:
                for peserta in session.attendee_ids:
                    print("======================= hasil", peserta.name, peserta.id)    
                    result.append(peserta.id)
            rec.write({'attendees_ids': [(6, 0, result)]})

    @api.depends('total_peserta')
    def _compute_total_pendapatan(self):
        for rec in self:
            total_pendapatan = rec.total_peserta * rec.harga_kursus
            # print("=====================", total_pendapatan)
            # print("=====================", rec.total_peserta * rec.harga_kursus)

            rec.total_pendapatan = total_pendapatan

    def _compute_total_peserta(self):
        for rec in self:
            if rec.session_line:
                total_peserta = rec.session_line.mapped('attendees_count')
                rec.total_peserta = sum(total_peserta) if total_peserta else 0
            else:
                rec.total_peserta = 0

    def _compute_total_hari(self):
        for rec in self:
            if rec.session_line:
                total_hari = rec.session_line.mapped('jumlah_hari')
                rec.total_hari = sum(total_hari) if total_hari else 0
            else:
                rec.total_hari = 0

    _sql_constraints = [
        ('nama_kursus_unik', 'UNIQUE(name)', 'Judul kursus harus unik'),
        ('nama_keterangan_cek', 'CHECK(name != description)', 'Judul kursus dan keterangan tidak boleh sama ')
    ]

    @api.model
    def create(self, vals):
        vals['ref'] = self.env['ir.sequence'].next_by_code('training.course')
        return super(TrainingCourse, self).create(vals)

    def copy(self, default=None):
        default = dict(default or {})
        default.update(name=("%s (copy)") % (self.name or ''))
        return super(TrainingCourse, self).copy(default)

    def action_print_course(self):
        return self.env.ref('training_odoo.report_training_course_action').report_action(self)
    

class TrainingSession(models.Model):
    _name = 'training.session'
    _description = 'Training Sesi'

    def default_partner_id(self):
        instruktur = self.env['res.partner'].search(['|', ('instructor', '=', True), ('category_id.name', 'ilike', 'Pengajar')], limit=1)
        return instruktur

    @api.depends('start_date', 'duration')
    def get_end_date(self):
        for sesi in self:
            if not sesi.start_date: 
                sesi.end_date = sesi.start_date
                continue

            start = fields.Date.from_string(sesi.start_date)
            sesi.end_date = start + timedelta(days=sesi.duration)
        
    def set_end_date(self):
        for sesi in self:
            if not (sesi.start_date and sesi.end_date):
                continue
            
            start_date = fields.Datetime.from_string(sesi.start_date)
            end_date = fields.Datetime.from_string(sesi.end_date)
            sesi.duration = (end_date - start_date).days + 1
            
    course_id = fields.Many2one('training.course', string='Judul Kursus', required=True, ondelete='cascade', readonly=True, states={'draft': [('readonly', False)]})
    name = fields.Char(string='Nama', required=True, readonly=True, states={'draft': [('readonly', False)]})
    start_date = fields.Date(string='Tanggal', default=fields.Date.context_today, readonly=True, states={'draft': [('readonly', False)]})
    duration = fields.Float(string='Durasi', help='Jumlah Hari Training', default=3, readonly=True, states={'draft': [('readonly', False)]})
    seats = fields.Integer(string='Kursi', help='Jumlah Kuota Kursi', default=10, readonly=True, states={'draft': [('readonly', False)]})
    partner_id = fields.Many2one('res.partner', string='Instruktur', domain=['|', ('instructor', '=', True), ('category_id.name', 'ilike', 'Pengajar')], default=default_partner_id, readonly=True, states={'draft': [('readonly', False)]})
    attendee_ids = fields.Many2many('training.attendee', 'session_attendee_rel', 'session_id', 'attendee_id', 'Peserta', readonly=True, states={'draft': [('readonly', False)]})
    end_date = fields.Date(string="Tanggal Selesai", compute='get_end_date', inverse='set_end_date', store=True, readonly=True, states={'draft': [('readonly', False)]})
    taken_seats = fields.Float(string="Kursi Terisi", compute='compute_taken_seats')
    attendees_count = fields.Integer(string="Jumlah Peserta", compute='get_attendees_count', store=True)
    color = fields.Integer('Index Warna', default=0)
    level = fields.Selection(string='Tingkatan', related='course_id.level')
    state = fields.Selection([('draft', 'Draft'), ('open', 'Open'), ('done', 'Done')], string='Status', readonly=True, default='draft')
    jumlah_kursi = fields.Char(compute='_compute_jumlah_kursi', string='Jumlah Kursi')
    jumlah_hari = fields.Integer(compute='_compute_jumlah_hari', string='Jumlah Hari')
    harga_kursus = fields.Monetary('Harga Kursus', related='course_id.harga_kursus')
    currency_id = fields.Many2one('res.currency', related='course_id.currency_id', string='Mata Uang', default=lambda self : self.env.company.currency_id)
    attendees_ids = fields.Many2many(string='Semua Peserta Kursus', related='course_id.attendees_ids')
    course_ids = fields.Many2many(comodel_name="training.course", string="Semua Kursus")
    all_attendees_course_ids = fields.Many2many('training.attendee', compute="_compute_all_attendees", string='Seluruh Peserta Kursus')

    def _compute_all_attendees(self):
        for rec in self:
            data = []
            for attendee in rec.course_ids.attendees_ids:
                data.append(attendee.id)
        self.all_attendees_course_ids = data

    # def _list_peserta(self):
    #     result = []
    #     for rec in self:
    #         for session in rec.session_line:
    #             for peserta in session.attendee_ids:
    #                 print("======================= hasil", peserta.name, peserta.id)
    #                 result.append(peserta.id)
    #         rec.write({'attendees_ids': [(6, 0, result)]})


    @api.depends('start_date', 'end_date')
    def _compute_jumlah_hari(self):
        for rec in self:
            if rec.start_date and rec.end_date:
                rec.jumlah_hari = (rec.end_date - rec.start_date).days
            
            else:
                rec.jumlah_hari = 0

    @api.depends('course_id')
    def _compute_jumlah_kursi(self):
        for rec in self:
            if rec.course_id:
                list_kursi = rec.course_id.session_line.mapped('seats')
                # print("================================", list_kursi)
                # print("================================", list_kursi)

                rec.jumlah_kursi = sum(list_kursi) if list_kursi else 0
            else:
                rec.jumlah_kursi = 0

    @api.onchange('course_id')
    def _onchange_course_id(self):
        for rec in self:
            for line in rec.course_id.session_line:
                line.name = "Test Ganti Nama"

    def action_print_session(self):
        return self.env.ref('training_odoo.report_training_session_action').report_action(self)

    # method name button print
    def action_print_session_draft(self):
        return self.env.ref('training_odoo.report_training_session_draft_action').report_action(self)

    def action_confirm(self):
        self.write({'state': 'open'})
    
    def action_cancel(self):
        self.write({'state': 'draft'})
    
    def action_close(self):
        self.write({'state': 'done'})

    @api.depends('attendee_ids')
    def get_attendees_count(self):
        for sesi in self:
            sesi.attendees_count = len(sesi.attendee_ids)

    @api.depends('seats', 'attendee_ids')
    def compute_taken_seats(self):
        for sesi in self:
            sesi.taken_seats = 0
            if sesi.seats and sesi.attendee_ids :
                sesi.taken_seats = 100 * len(sesi.attendee_ids) / sesi.seats
                print(" =========================== ada orang nih")
            else:
                print("******************* kelas sepi nih")

    @api.constrains('seats', 'attendee_ids')
    def check_seats_and_attendees(self):
        for r in self:
            if r.seats < len(r.attendee_ids): 
                raise ValidationError("Jumlah peserta melebihi kuota yang disediakan")

    @api.onchange('duration')
    def verify_valid_duration(self):
        if self.duration <= 0:
            self.duration = 1
            return {'warning': {'title': 'Perhatian', 'message': 'Durasi Hari Training Tidak Boleh 0 atau Negatif'}}

    def cron_expire_session(self):
        now = fields.Date.today()
        expired_ids = self.search([('end_date', '<', now), ('state', '=', 'open')])
        expired_ids.write({'state': 'done'})


class TrainingAttendee(models.Model):
    _name = 'training.attendee'
    _description = 'Training Peserta'
    _inherits = {'res.partner': 'partner_id'}

    partner_id = fields.Many2one('res.partner', 'Partner', required=True, ondelete='cascade')
    name = fields.Char(string='Nama', required=True, inherited=True)
    sex = fields.Selection([('male', 'Pria'), ('female', 'Wanita')], string='Kelamin', required=True, help='Jenis Kelamin')
    marital = fields.Selection([
        ('single', 'Belum Menikah'),
        ('married', 'Menikah'),
        ('divorced', 'Cerai')],
        string='Pernikahan', help='Status Pernikahan')
    session_ids = fields.Many2many('training.session', 'session_attendee_rel', 'attendee_id', 'session_id', 'Sesi')
    course_id = fields.Many2one(comodel_name="training.course")