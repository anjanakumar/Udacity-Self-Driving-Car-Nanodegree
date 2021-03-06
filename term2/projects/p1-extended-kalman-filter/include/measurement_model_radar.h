#ifndef MEASUREMENT_MODEL_RADAR_H
#define MEASUREMENT_MODEL_RADAR_H

#include "measurement_model.h"

static const double noise_range_      = 0.09;   // [m]^2
static const double noise_bearing_    = 0.0009; // [rad]^2
static const double noise_range_rate_ = 0.09;   // [m/s]^2

class MeasurementModelRadar : public MeasurementModel
{
public:
    /// \brief Constructor
    /// \param n_states dimension of the state vector
    MeasurementModelRadar(const std::size_t n_states);
    virtual ~MeasurementModelRadar();

    /// \brief Computes z_hat = h(x')
    /// \param state predicted state, x'
    /// \return the predicted measurement, z_hat
    virtual Eigen::VectorXd predictMeasurement(const Eigen::VectorXd& state) const;

    virtual Eigen::VectorXd computeResidual(const Eigen::VectorXd& z,
                                            const Eigen::VectorXd& z_hat) const;

    /// \brief Computes and returns the measurement matrix, H
    /// \param state predicted state, x'
    /// \return the H matrix
    virtual Eigen::MatrixXd getH(const Eigen::VectorXd &state) const;

    /// \brief Computes and returns the measurement noise matrix, R
    /// \return the R matrix
    virtual Eigen::MatrixXd getR() const;

private:
    const std::size_t n_observed_states_ = 3U;
};

#endif // MEASUREMENT_MODEL_RADAR_H
