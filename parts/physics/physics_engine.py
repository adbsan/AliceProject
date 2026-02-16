import pymunk
from parts.config import Config

class PhysicsEngine:
    def __init__(self):
        self.space = pymunk.Space()
        self.space.gravity = Config.GRAVITY 
        self._setup_boundaries()
        self.character_body = None
        self.character_shape = None
        self._add_character()
        self.mouse_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        self.mouse_joint = None

    def _setup_boundaries(self):
        w, h = Config.WINDOW_WIDTH, 600
        # Pymunk最新版対応: list()でラップ
        for shape in list(self.space.shapes):
            if isinstance(shape, pymunk.Segment):
                self.space.remove(shape)

        lines = [
            pymunk.Segment(self.space.static_body, (0, h), (w, h), 10),
            pymunk.Segment(self.space.static_body, (0, 0), (w, 0), 10),
            pymunk.Segment(self.space.static_body, (0, 0), (0, h), 10),
            pymunk.Segment(self.space.static_body, (w, 0), (w, h), 10)
        ]
        for line in lines:
            line.elasticity, line.friction = 0.5, 0.5
            self.space.add(line)

    def _add_character(self):
        width, height = Config.CHARACTER_DISPLAY_SIZE
        mass, moment = 1.0, pymunk.moment_for_box(1.0, (width * 0.7, height * 0.7))
        self.character_body = pymunk.Body(mass, moment)
        self.character_body.position = (Config.WINDOW_WIDTH // 2, 300)
        self.character_shape = pymunk.Poly.create_box(self.character_body, (width * 0.7, height * 0.7))
        self.character_shape.elasticity, self.character_shape.friction = 0.3, 0.6
        self.space.add(self.character_body, self.character_shape)

    def step(self):
        self.space.step(1.0 / Config.PHYSICS_FPS)

    def get_character_transform(self):
        return self.character_body.position.x, self.character_body.position.y, self.character_body.angle

    def start_dragging(self, x, y):
        self.mouse_body.position = (x, y)
        if self.mouse_joint: self.space.remove(self.mouse_joint)
        self.mouse_joint = pymunk.PivotJoint(self.mouse_body, self.character_body, (x, y))
        self.mouse_joint.max_force = 1000000
        self.space.add(self.mouse_joint)

    def update_drag_pos(self, x, y):
        self.mouse_body.position = (x, y)

    def stop_dragging(self):
        if self.mouse_joint:
            self.space.remove(self.mouse_joint)
            self.mouse_joint = None

    def apply_impulse(self, fx, fy):
        self.character_body.apply_impulse_at_local_point((fx, fy))