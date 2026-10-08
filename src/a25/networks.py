"""Source-shared learned material updates and the paper SOM-Net flow.

N0 follows Fig. 2/Algorithm 1 of arXiv:2209.03567: four separate current
CNNs, exact G-field updates, and one material ratio over all sources.  Its
64/128/256 bottleneck choice records the figure's unlabeled bottom width.
N1/N2/N3 have identical parameterized modules and channel definitions.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn

from .torch_physics import (TorchReference, TorchRelativeModel, TorchState,
                            mass_pack, mass_unpack)


FEATURE_NAMES = ("chi_real", "chi_imag", "data_gradient_mass_real",
                 "data_gradient_mass_imag", "source_mean_field_power",
                 "source_mean_current_power", "initial_chi_real",
                 "initial_chi_imag", "background_real", "background_imag")


class DoubleConv(nn.Module):
    def __init__(self, incoming, outgoing):
        super().__init__()
        self.body = nn.Sequential(
            nn.Conv2d(incoming, outgoing, 3, padding=1), nn.BatchNorm2d(outgoing), nn.ReLU(),
            nn.Conv2d(outgoing, outgoing, 3, padding=1), nn.BatchNorm2d(outgoing), nn.ReLU())

    def forward(self, value):
        return self.body(value)


class UNet2(nn.Module):
    """Two down/up levels, matching the published SOM-Net figure topology."""
    def __init__(self, incoming, outgoing=2, width=32):
        super().__init__()
        width = int(width)
        self.encoder1 = DoubleConv(incoming, width)
        self.encoder2 = DoubleConv(width, 2 * width)
        self.bottom = DoubleConv(2 * width, 4 * width)
        self.pool = nn.MaxPool2d(2)
        self.up2 = nn.ConvTranspose2d(4 * width, 2 * width, 2, stride=2)
        self.decoder2 = DoubleConv(4 * width, 2 * width)
        self.up1 = nn.ConvTranspose2d(2 * width, width, 2, stride=2)
        self.decoder1 = DoubleConv(2 * width, width)
        self.output = nn.Conv2d(width, outgoing, 1)

    def forward(self, value):
        if value.dtype != torch.float32 or value.shape[-1] % 4 or value.shape[-2] % 4:
            raise ValueError("FLOAT32_GRID_MULTIPLE_OF_FOUR_REQUIRED")
        first = self.encoder1(value)
        second = self.encoder2(self.pool(first))
        bottom = self.bottom(self.pool(second))
        decoded = self.decoder2(torch.cat((self.up2(bottom), second), dim=1))
        return self.output(self.decoder1(torch.cat((self.up1(decoded), first), dim=1)))


class FeatureNormalizer(nn.Module):
    """Statistics fit on legal training observations/labels only, then frozen."""
    def __init__(self):
        super().__init__()
        self.register_buffer("mean", torch.zeros(1, len(FEATURE_NAMES), 1, 1, dtype=torch.float64))
        self.register_buffer("std", torch.ones_like(self.mean))
        self.register_buffer("som_mean", torch.zeros(1, 4, 1, 1, dtype=torch.float64))
        self.register_buffer("som_std", torch.ones_like(self.som_mean))
        self.register_buffer("material_scale", torch.tensor(1., dtype=torch.float64))
        self.register_buffer("current_scale", torch.tensor(1., dtype=torch.float64))
        self.register_buffer("fitted", torch.tensor(False))
        self.provenance = {"role": "UNFITTED_HEALTH_ONLY"}

    def fit_statistics(self, feature_sum, feature_square_sum, feature_count,
                       som_sum, som_square_sum, som_count, *, material_scale,
                       current_scale, parent_ids, role="train"):
        if role != "train" or bool(self.fitted):
            raise ValueError("NORMALIZER_FIT_REQUIRES_UNFITTED_TRAIN_ROLE")
        if feature_count <= 0 or som_count <= 0:
            raise ValueError("NONEMPTY_TRAIN_STATISTICS_REQUIRED")
        with torch.no_grad():
            mean = feature_sum / feature_count
            variance = feature_square_sum / feature_count - mean.square()
            som_mean = som_sum / som_count
            som_variance = som_square_sum / som_count - som_mean.square()
            self.mean.copy_(mean.reshape_as(self.mean))
            self.std.copy_(variance.clamp_min(1e-12).sqrt().reshape_as(self.std))
            self.som_mean.copy_(som_mean.reshape_as(self.som_mean))
            self.som_std.copy_(som_variance.clamp_min(1e-12).sqrt().reshape_as(self.som_std))
            self.material_scale.fill_(max(float(material_scale), 1e-6))
            self.current_scale.fill_(max(float(current_scale), 1e-12))
            self.fitted.fill_(True)
        self.provenance = {"role": "train", "parent_ids": sorted(set(map(int, parent_ids))),
                           "feature_names": list(FEATURE_NAMES), "minimum_std": 1e-6}

    def forward(self, value, *, som=False):
        mean, std = (self.som_mean, self.som_std) if som else (self.mean, self.std)
        return ((value.to(torch.float64) - mean) / std).to(torch.float32)


def symmetric_features(reference, mass, gradient, state, initial_mass):
    """Ten channels; source permutations leave their sums/means unchanged."""
    chi = mass_unpack(mass, reference.volume)
    initial = mass_unpack(initial_mass, reference.volume)
    n = reference.n
    material = torch.stack((chi.real, chi.imag), dim=1)
    grad = torch.stack((gradient[:, :n], gradient[:, n:]), dim=1)
    field_power = state.field.abs().square().mean(-1)[:, None]
    current_power = reference.canonical_current(state).abs().square().mean(-1)[:, None]
    init = torch.stack((initial.real, initial.imag), dim=1)
    background = torch.stack((reference.chi_b.real, reference.chi_b.imag), dim=0)
    background = background[None].expand(len(mass), -1, -1)
    return torch.cat((material, grad, field_power, current_power, init, background), dim=1).reshape(len(mass), len(FEATURE_NAMES), reference.grid, reference.grid)


def som_channels(current, mass, reference):
    """One source sample contains current Re/Im and common permittivity Re/Im."""
    chi = mass_unpack(mass, reference.volume)
    channels = torch.stack((current.real.transpose(1, 2), current.imag.transpose(1, 2),
                            (1. + chi.real)[:, None].expand(-1, reference.s, -1),
                            chi.imag[:, None].expand(-1, reference.s, -1)), dim=2)
    return channels.reshape(len(mass) * reference.s, 4, reference.grid, reference.grid)


@dataclass
class NetworkResult:
    mass: torch.Tensor
    chi: torch.Tensor
    data: torch.Tensor
    current: torch.Tensor
    states: list[TorchState]
    stages: list[torch.Tensor]
    diagnostics: dict


class LearnedImager(nn.Module):
    def __init__(self, references, kind, *, normalizer=None, blocks=3, width=32,
                 prior_scale=.25, observable_rank=15):
        super().__init__()
        self.kind = str(kind).upper()
        if self.kind not in {"N0", "N1", "N2", "N3"}:
            raise ValueError("UNKNOWN_A25_NETWORK")
        if not references:
            raise ValueError("BACKGROUND_REFERENCES_REQUIRED")
        self.references = nn.ModuleDict({str(k): v for k, v in references.items()})
        self.normalizer = FeatureNormalizer() if normalizer is None else normalizer
        self.blocks = 4 if self.kind == "N0" else int(blocks)
        if self.kind != "N0" and self.blocks not in {3, 4}:
            raise ValueError("A25_ONLY_THREE_OR_FOUR_MATERIAL_BLOCKS")
        self.width = 64 if self.kind == "N0" else int(width)
        self.prior_scale, self.observable_rank = float(prior_scale), int(observable_rank)
        self.stages = nn.ModuleList([UNet2(4 if self.kind == "N0" else len(FEATURE_NAMES),
                                         2, self.width) for _ in range(self.blocks)])
        closure = "R" if self.kind == "N2" else "L"
        # References are registered once; these parameter-free wrappers share them.
        self._physics = {key: TorchRelativeModel(ref, closure) for key, ref in self.references.items()}
        first = next(iter(self.references.values()))
        self.grid, self.n, self.q, self.s, self.volume = first.grid, first.n, first.q, first.s, first.volume
        if any((ref.grid, ref.q, ref.s, ref.volume) != (self.grid, self.q, self.s, self.volume)
               for ref in self.references.values()):
            raise ValueError("COMMON_GRID_APERTURE_AND_NORMALIZATION_REQUIRED")
        self.metadata = {"method": self.kind, "blocks": self.blocks, "width": self.width,
                         "material_state": "real_mass_full_grid", "CNN_dtype": "float32",
                         "physics_dtype": "complex128/float64", "feature_names": list(FEATURE_NAMES),
                         "N0_paper": "https://arxiv.org/abs/2209.03567",
                         "N0_backbone_bottom_width": "256 inferred from unlabeled Fig2 bottleneck",
                         "N0_lossy_channels": 4, "N0_official_implementation": False,
                         "N0_initial_material": "shared certified initializer, disclosed adaptation",
                         "N3_recurrence": "learned material increment with L features; no explicit gradient step",
                         "TV_role": "shared initialization and loss; no proximal certificate for CNN blocks"}

    @property
    def parameter_count(self):
        return sum(parameter.numel() for parameter in self.parameters() if parameter.requires_grad)

    @property
    def book(self):
        return next(iter(self.references.values())).book

    def bind_book(self, book):
        for reference in self.references.values():
            reference.bind_book(book)
        return self

    def _groups(self, background_ids, device):
        labels = [str(value) for value in background_ids]
        if set(labels) - set(self.references):
            raise ValueError("UNREGISTERED_BACKGROUND")
        return {key: torch.tensor([i for i, label in enumerate(labels) if label == key],
                                  dtype=torch.long, device=device)
                for key in sorted(set(labels))}

    def _initial(self, observation, groups, initial_mass):
        if initial_mass is None:
            raise ValueError("SHARED_CERTIFIED_INITIAL_MASS_REQUIRED")
        if initial_mass.shape != (len(observation), 2 * self.n) or initial_mass.dtype != torch.float64:
            raise ValueError("FLOAT64_BATCH_INITIAL_MASS_REQUIRED")
        # A differentiable identity, never a state-dependent stop-gradient.
        return initial_mass.clone()

    def feature_batch(self, observation, background_ids, mass, initial_mass):
        groups = self._groups(background_ids, mass.device)
        features = torch.zeros((len(mass), len(FEATURE_NAMES), self.grid, self.grid),
                               dtype=torch.float64, device=mass.device)
        gradients = torch.zeros_like(mass)
        states = {}
        for key, indices in groups.items():
            ref, model = self.references[key], self._physics[key]
            value = mass.index_select(0, indices)
            state = model(value)
            gradient = model.data_gradient(value, observation.index_select(0, indices), state)
            local = symmetric_features(ref, value, gradient, state, initial_mass.index_select(0, indices))
            features = features.index_copy(0, indices, local)
            gradients = gradients.index_copy(0, indices, gradient)
            states[key] = state
        return features, gradients, states

    def forward(self, observation, background_ids, *, initial_mass, report_consistency=False):
        if observation.dtype != torch.complex128 or observation.shape[1:] != (self.q, self.s):
            raise ValueError("COMPLEX128_BATCH_Q_SOURCE_OBSERVATION_REQUIRED")
        groups = self._groups(background_ids, observation.device)
        mass = self._initial(observation, groups, initial_mass)
        with self.book.span("network_" + self.kind + "_forward", network_images=len(observation),
                            CNN_block_images=len(observation) * self.blocks * (self.s if self.kind == "N0" else 1)):
            if self.kind == "N0":
                return self._som_forward(observation, groups, mass, report_consistency)
            history = []
            for block in self.stages:
                features, gradients, _ = self.feature_batch(observation, background_ids, mass, initial_mass)
                learned = block(self.normalizer(features)).to(torch.float64)
                learned = torch.complex(learned[:, 0].flatten(1), learned[:, 1].flatten(1))
                increment = mass_pack(learned * self.prior_scale * self.normalizer.material_scale, self.volume)
                proposed = mass + increment
                if self.kind != "N3":
                    for key, indices in groups.items():
                        gradient_step = self.references[key].step * gradients.index_select(0, indices)
                        proposed = proposed.index_add(0, indices, -gradient_step)
                mass = self._project_groups(proposed, groups)
                history.append(mass)
            states = {key: self._physics[key](mass.index_select(0, indices))
                      for key, indices in groups.items()}
            return self._assemble(mass, groups, states, history, report_consistency)

    def _project_groups(self, mass, groups):
        out = torch.zeros_like(mass)
        for key, indices in groups.items():
            out = out.index_copy(0, indices, self.references[key].project(mass.index_select(0, indices)))
        return out

    def _som_forward(self, observation, groups, mass, report_consistency):
        current = torch.zeros((len(mass), self.n, self.s), dtype=torch.complex128, device=mass.device)
        for key, indices in groups.items():
            ref = self.references[key]
            ref.prepare_observable(self.observable_rank)
            y = observation.index_select(0, indices)
            with self.book.span("torch_SOM_deterministic_current", deterministic_current_source_rhs=len(indices) * self.s):
                c = ref.observable_right @ ((ref.observable_left.mH @ y) / ref.observable_singular[:, None])
            current = current.index_copy(0, indices, c)
        history, states = [], {}
        for block in self.stages:
            ref0 = next(iter(self.references.values()))
            channels = som_channels(current, mass, ref0)
            learned = block(self.normalizer(channels, som=True)).to(torch.float64)
            c = torch.complex(learned[:, 0].flatten(1), learned[:, 1].flatten(1))
            current = (self.normalizer.current_scale * c).reshape(len(mass), self.s, self.n).transpose(1, 2)
            for key, indices in groups.items():
                ref = self.references[key]
                local_current = current.index_select(0, indices)
                field = ref.incident + ref.green(local_current)
                local_mass = ref.project(ref.material_ratio(local_current, field))
                mass = mass.index_copy(0, indices, local_mass)
                chi = mass_unpack(local_mass, ref.volume)
                w = ref.apply(ref.Lb, local_current - ref.cb, "reference_L")
                states[key] = TorchState(local_mass, chi, chi - ref.chi_b,
                                         ref.observe(local_current), w, field,
                                         current=local_current, canonical_field=field,
                                         extra={"current_learning": True})
            history.append(mass)
        return self._assemble(mass, groups, states, history, report_consistency)

    def _assemble(self, mass, groups, states, history, report_consistency):
        data = torch.zeros((len(mass), self.q, self.s), dtype=torch.complex128, device=mass.device)
        current = torch.zeros((len(mass), self.n, self.s), dtype=torch.complex128, device=mass.device)
        ordered = [None] * len(mass)
        diagnostics = {}
        for key, indices in groups.items():
            state = states[key]
            data = data.index_copy(0, indices, state.data)
            current = current.index_copy(0, indices, self.references[key].canonical_current(state))
            if report_consistency:
                diagnostics[key] = self.references[key].consistency(state)
            for position, index in enumerate(indices.tolist()):
                ordered[index] = TorchState(state.mass[position], state.chi[position], state.h[position],
                                           state.data[position], state.w[position], state.field[position],
                                           margins=state.margins, extra={"background_id": key},
                                           current=state.current[position])
        return NetworkResult(mass, mass_unpack(mass, self.volume), data, current,
                             ordered, history, diagnostics)

    def learned_state_dict(self):
        return {key: value for key, value in self.state_dict().items()
                if not key.startswith("references.")}

    def load_learned_state_dict(self, state):
        result = self.load_state_dict(state, strict=False)
        missing = [key for key in result.missing_keys if not key.startswith("references.")]
        if missing or result.unexpected_keys:
            raise ValueError("LEARNED_CHECKPOINT_TOPOLOGY_MISMATCH")


def build_model(kind, references, *, normalizer=None, config=None, blocks=None):
    config = dict(config or {})
    training = config.get("training", config)
    return LearnedImager(references, kind, normalizer=normalizer,
                         blocks=int(training.get("main_blocks", 3) if blocks is None else blocks),
                         width=int(training.get("material_width", 32)),
                         prior_scale=float(training.get("prior_scale", .25)),
                         observable_rank=int(training.get("som_observable_rank", 15)))


def assert_parameter_match(models, tolerance=.05):
    selected = [model for model in models if model.kind in {"N1", "N2", "N3"}]
    if len(selected) != 3 or len({model.blocks for model in selected}) != 1:
        raise ValueError("ALL_THREE_MATCHED_METHODS_AT_ONE_DEPTH_REQUIRED")
    counts = {model.kind: model.parameter_count for model in selected}
    if max(counts.values()) / min(counts.values()) - 1 > float(tolerance):
        raise ValueError("EFFECTIVE_PARAMETER_MATCH_FAILED")
    return counts
